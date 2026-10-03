package com.teja.gemmmobile.assistant

import android.content.Context
import android.util.Log
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File

private const val TAG = "ContactMemory"
private const val CONTACT_MEMORY_FILE = "remembered_contacts.json"

data class RememberedContact(
    val queryKey: String,           // e.g. "teja", "manoj", "nanna", "aparna"
    val fullName: String,           // e.g. "Teja Pampana"
    val phoneNumber: String,        // e.g. "919542696946"
    val formattedNumber: String,    // e.g. "+91 95426 96946"
    val lastUsedAt: Long = System.currentTimeMillis()
)

object ContactMemoryManager {
    private val gson = Gson()
    private val memoryMap = mutableMapOf<String, RememberedContact>()
    private var isInitialized = false

    private fun getFile(context: Context): File = File(context.filesDir, CONTACT_MEMORY_FILE)

    @Synchronized
    fun initialize(context: Context) {
        if (isInitialized) return
        try {
            val file = getFile(context)
            if (file.exists() && file.length() > 0) {
                val json = file.readText()
                val type = object : TypeToken<Map<String, RememberedContact>>() {}.type
                val map: Map<String, RememberedContact>? = gson.fromJson(json, type)
                if (map != null) {
                    memoryMap.putAll(map)
                }
            }
            isInitialized = true
            Log.d(TAG, "[$TAG] Initialized with ${memoryMap.size} remembered contacts")
        } catch (e: Exception) {
            Log.e(TAG, "[$TAG] Error loading remembered contacts", e)
        }
    }

    /**
     * Finds a remembered contact for the given name or nickname.
     */
    fun getRememberedContact(context: Context, query: String): ContactMatch? {
        initialize(context)
        val clean = query.trim().lowercase()
        val found = memoryMap[clean] ?: memoryMap.values.find {
            it.fullName.equals(clean, ignoreCase = true) ||
            it.fullName.lowercase().contains(clean) ||
            clean.contains(it.queryKey)
        } ?: return null

        return ContactMatch(
            name = found.fullName,
            phoneNumber = found.phoneNumber,
            formattedNumber = found.formattedNumber
        )
    }

    /**
     * Remembers a contact mapping so Gemma instantly recognizes this person in the future.
     */
    fun rememberContact(
        context: Context,
        queryKey: String,
        fullName: String,
        phoneNumber: String,
        formattedNumber: String
    ) {
        initialize(context)
        val cleanKey = queryKey.trim().lowercase()
        val item = RememberedContact(
            queryKey = cleanKey,
            fullName = fullName,
            phoneNumber = phoneNumber,
            formattedNumber = formattedNumber,
            lastUsedAt = System.currentTimeMillis()
        )
        memoryMap[cleanKey] = item
        // Also index by first word of name
        val firstName = fullName.split(" ").firstOrNull()?.trim()?.lowercase()
        if (!firstName.isNullOrBlank() && firstName != cleanKey) {
            memoryMap[firstName] = item
        }

        saveToDisk(context)
        Log.d(TAG, "[$TAG] Remembered contact: $cleanKey -> $fullName ($formattedNumber)")
    }

    private fun saveToDisk(context: Context) {
        try {
            val file = getFile(context)
            val json = gson.toJson(memoryMap)
            file.writeText(json)
        } catch (e: Exception) {
            Log.e(TAG, "[$TAG] Error saving remembered contacts", e)
        }
    }

    fun getAllRemembered(context: Context): List<RememberedContact> {
        initialize(context)
        return memoryMap.values.distinctBy { it.phoneNumber }.sortedByDescending { it.lastUsedAt }
    }
}
