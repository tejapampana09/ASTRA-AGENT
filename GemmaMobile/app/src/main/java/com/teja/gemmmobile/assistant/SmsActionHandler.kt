package com.teja.gemmmobile.assistant

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.telephony.SmsManager
import android.util.Log
import androidx.core.content.ContextCompat

private const val TAG = "SmsActionHandler"

object SmsActionHandler {

    /**
     * Checks if a user prompt is asking to send a message / SMS / text.
     * Returns Pair(recipientName, messageBody).
     */
    fun parseMessageIntent(prompt: String): Pair<String, String>? {
        val trimmed = prompt.trim()

        // 1. "send a message to <contact> that/saying <msg>" / "send message to <contact> <msg>"
        val p1 = Regex("""^(?:please\s+)?send\s+(?:a\s+)?(?:text\s+|sms\s+|message\s+)?to\s+([a-zA-Z0-9_\s]+?)\s+(?:saying|that|:)\s+(.+)$""", RegexOption.IGNORE_CASE)
        p1.find(trimmed)?.let { m ->
            val contact = m.groupValues[1].trim()
            val msg = m.groupValues[2].trim('\'', '"', ' ')
            if (contact.isNotBlank() && msg.isNotBlank()) return Pair(contact, msg)
        }

        // 2. "message <contact> <msg>" / "text <contact> <msg>" / "sms <contact> <msg>"
        val p2 = Regex("""^(?:please\s+)?(?:message|text|sms)\s+([a-zA-Z0-9_]+)\s+(?:saying|that|:)?\s*(.+)$""", RegexOption.IGNORE_CASE)
        p2.find(trimmed)?.let { m ->
            val contact = m.groupValues[1].trim()
            val msg = m.groupValues[2].trim('\'', '"', ' ')
            if (contact.isNotBlank() && msg.isNotBlank() && !contact.equals("to", ignoreCase = true)) {
                return Pair(contact, msg)
            }
        }

        // 3. "send <msg> to <contact>" (excluding if explicit "whatsapp" is mentioned)
        if (!trimmed.contains("whatsapp", ignoreCase = true)) {
            val p3 = Regex("""^(?:please\s+)?send\s+(.+?)\s+to\s+([a-zA-Z0-9_\s]+)$""", RegexOption.IGNORE_CASE)
            p3.find(trimmed)?.let { m ->
                val msg = m.groupValues[1].trim('\'', '"', ' ')
                val contact = m.groupValues[2].trim()
                if (contact.isNotBlank() && msg.isNotBlank()) return Pair(contact, msg)
            }
        }

        // 4. Telugu patterns:
        // "<contact> ki message cheyi <msg>" / "<contact> ki sms pettu <msg>"
        val telugu1 = Regex("""^([a-zA-Z0-9_]+)\s*(?:ki|ku)\s+(?:message|sms)\s+(?:cheyi|cheyyi|pettu|pampinchu)\s*(?:ani\s+)?(.+)$""", RegexOption.IGNORE_CASE)
        telugu1.find(trimmed)?.let { m ->
            val contact = m.groupValues[1].trim()
            val msg = m.groupValues[2].trim('\'', '"', ' ')
            if (contact.isNotBlank() && msg.isNotBlank()) return Pair(contact, msg)
        }

        // "<contact> ki <msg> ani message pettu" / "<contact> ki <msg> pettu" (if not mentioning whatsapp)
        if (!trimmed.contains("whatsapp", ignoreCase = true)) {
            val telugu2 = Regex("""^([a-zA-Z0-9_]+)\s*(?:ki|ku)\s+(.+?)\s*(?:ani\s+)?(?:message|sms|pettu|cheppu|pampinchu)$""", RegexOption.IGNORE_CASE)
            telugu2.find(trimmed)?.let { m ->
                val contact = m.groupValues[1].trim()
                val msg = m.groupValues[2].trim('\'', '"', ' ')
                if (contact.isNotBlank() && msg.isNotBlank() && !msg.equals("call", ignoreCase = true) && !msg.equals("phone", ignoreCase = true)) {
                    return Pair(contact, msg)
                }
            }
        }

        return null
    }

    /**
     * Sends an SMS 100% silently in the background without opening ANY application.
     */
    fun sendSmsDirect(context: Context, phoneNumber: String, message: String): Boolean {
        return try {
            val hasPermission = ContextCompat.checkSelfPermission(
                context,
                Manifest.permission.SEND_SMS
            ) == PackageManager.PERMISSION_GRANTED
            if (!hasPermission) {
                Log.w(TAG, "[$TAG] SEND_SMS permission not granted")
                return false
            }

            val targetNumber = ContactHelper.normalizePhoneNumber(phoneNumber).ifBlank { phoneNumber.trim() }
            val formatted = if (targetNumber.matches(Regex("""^91\d{10}$"""))) "+$targetNumber" else targetNumber

            val smsManager: SmsManager = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                context.getSystemService(SmsManager::class.java)
            } else {
                @Suppress("DEPRECATION")
                SmsManager.getDefault()
            }

            val parts = smsManager.divideMessage(message)
            if (parts.size > 1) {
                smsManager.sendMultipartTextMessage(formatted, null, parts, null, null)
            } else {
                smsManager.sendTextMessage(formatted, null, message, null, null)
            }
            Log.d(TAG, "[$TAG] SMS sent successfully in background to $formatted")
            true
        } catch (e: Exception) {
            Log.e(TAG, "[$TAG] Failed to send SMS in background", e)
            false
        }
    }
}
