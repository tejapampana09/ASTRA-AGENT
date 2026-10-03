package com.teja.gemmmobile.assistant

import android.content.Context
import android.database.Cursor
import android.provider.ContactsContract
import android.util.Log

private const val TAG = "ContactHelper"

data class ContactMatch(
    val name: String,
    val phoneNumber: String,
    val formattedNumber: String
)

object ContactHelper {

    /**
     * Searches device contacts for matches matching the given contact name.
     * Incorporates persistent ContactMemoryManager so previously used or confirmed contacts are prioritized.
     */
    fun searchContact(context: Context, queryName: String): List<ContactMatch> {
        val results = mutableListOf<ContactMatch>()
        val cleanQuery = queryName.trim().lowercase()
        if (cleanQuery.isBlank()) return emptyList()

        // 1. Check remembered contacts first (e.g. previously confirmed "Teja", "Manoj", nicknames)
        val remembered = ContactMemoryManager.getRememberedContact(context, cleanQuery)
        if (remembered != null) {
            results.add(remembered)
        }

        try {
            val contentResolver = context.contentResolver
            val projection = arrayOf(
                ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME,
                ContactsContract.CommonDataKinds.Phone.NUMBER
            )

            // Read contacts to perform case-insensitive and multi-word boundary matching in memory
            val cursor: Cursor? = contentResolver.query(
                ContactsContract.CommonDataKinds.Phone.CONTENT_URI,
                projection,
                null,
                null,
                "${ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME} ASC"
            )

            cursor?.use {
                val nameIndex = it.getColumnIndex(ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME)
                val numberIndex = it.getColumnIndex(ContactsContract.CommonDataKinds.Phone.NUMBER)

                while (it.moveToNext()) {
                    val name = if (nameIndex != -1) it.getString(nameIndex) ?: "" else ""
                    val rawNumber = if (numberIndex != -1) it.getString(numberIndex) ?: "" else ""

                    if (name.isBlank() || rawNumber.isBlank()) continue

                    val nameLower = name.lowercase()
                    val isMatch = nameLower.contains(cleanQuery) ||
                            nameLower.split(" ", "_", "-", ".", "@").any { word ->
                                word.startsWith(cleanQuery) || cleanQuery.startsWith(word)
                            }

                    if (isMatch) {
                        val normalized = normalizePhoneNumber(rawNumber)
                        if (normalized.isNotBlank()) {
                            // Avoid duplicates
                            if (results.none { r -> r.phoneNumber == normalized }) {
                                results.add(
                                    ContactMatch(
                                        name = name,
                                        phoneNumber = normalized,
                                        formattedNumber = rawNumber.trim()
                                    )
                                )
                            }
                        }
                    }
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "[$TAG] Error querying contacts", e)
        }

        // Sort by relevance:
        // 1. Exactly equals query
        // 2. Starts with query
        // 3. Word starts with query
        // 4. Substring match
        return results.sortedWith(
            compareByDescending<ContactMatch> {
                when {
                    remembered?.phoneNumber == it.phoneNumber -> 1000
                    it.name.equals(cleanQuery, ignoreCase = true) -> 500
                    it.name.startsWith(cleanQuery, ignoreCase = true) -> 300
                    it.name.split(" ", "_", "-", ".").any { w -> w.equals(cleanQuery, ignoreCase = true) } -> 200
                    it.name.split(" ", "_", "-", ".").any { w -> w.startsWith(cleanQuery, ignoreCase = true) } -> 100
                    else -> 50
                }
            }
        )
    }

    /**
     * Normalizes phone number into international format suitable for WhatsApp API (e.g. 919876543210).
     */
    fun normalizePhoneNumber(raw: String): String {
        // Strip everything except digits
        var digits = raw.replace(Regex("[^0-9]"), "")
        if (digits.isBlank()) return ""

        // If it starts with 00 (e.g. 0091...), remove 00
        if (digits.startsWith("00")) {
            digits = digits.substring(2)
        }

        // If it's a 10 digit number (standard in India), assume country code 91
        if (digits.length == 10) {
            digits = "91$digits"
        }

        // If it's 11 digits starting with 0, replace leading 0 with 91
        if (digits.length == 11 && digits.startsWith("0")) {
            digits = "91" + digits.substring(1)
        }

        return digits
    }
}
