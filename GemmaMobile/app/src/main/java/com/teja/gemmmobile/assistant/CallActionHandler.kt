package com.teja.gemmmobile.assistant

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.util.Log
import androidx.core.content.ContextCompat

private const val TAG = "CallActionHandler"

data class CallAction(
    val recipientName: String,
    val matchedNumber: String? = null,
    val candidateContacts: List<ContactMatch> = emptyList(),
    val status: CallStatus = CallStatus.AWAITING_CONFIRMATION
)

enum class CallStatus {
    AWAITING_CONFIRMATION,
    CALLING,
    DIALED,
    FAILED,
    NO_CONTACT_FOUND,
    CANCELLED
}

object CallActionHandler {

    /**
     * Checks if a user prompt is asking to make a phone call and extracts the target contact or number.
     */
    fun parseCallIntent(prompt: String): String? {
        val trimmed = prompt.trim()

        // 1. "call <contact or number>"
        // e.g. "call manoj", "call suhas", "call 9542696946", "please call nanna"
        val callRegex1 = Regex("""^(?:please\s+)?call\s+(.+)$""", RegexOption.IGNORE_CASE)
        callRegex1.find(trimmed)?.let { match ->
            val target = match.groupValues[1].trim('\'', '"', ' ')
            if (target.isNotBlank()) return target
        }

        // 2. "make a call to <contact or number>" / "make a phone call to <contact>"
        val callRegex2 = Regex("""^(?:please\s+)?make\s+(?:a\s+)?(?:phone\s+)?call\s+(?:to\s+)?(.+)$""", RegexOption.IGNORE_CASE)
        callRegex2.find(trimmed)?.let { match ->
            val target = match.groupValues[1].trim('\'', '"', ' ')
            if (target.isNotBlank()) return target
        }

        // 3. "phone <contact>"
        val phoneRegex = Regex("""^(?:please\s+)?phone\s+([a-zA-Z0-9_\s]+)$""", RegexOption.IGNORE_CASE)
        phoneRegex.find(trimmed)?.let { match ->
            val target = match.groupValues[1].trim()
            if (target.isNotBlank() && !target.equals("number", ignoreCase = true)) return target
        }

        // 4. "dial <number or contact>"
        val dialRegex = Regex("""^(?:please\s+)?dial\s+(.+)$""", RegexOption.IGNORE_CASE)
        dialRegex.find(trimmed)?.let { match ->
            val target = match.groupValues[1].trim()
            if (target.isNotBlank()) return target
        }

        // 5. Telugu patterns:
        // "<contact> ki call cheyi" / "manoj ki call cheyyi" / "manoj ki phone cheyi"
        val teluguRegex1 = Regex("""^(.+?)\s*(?:ki|ku)\s+(?:call|phone)\s*(?:cheyi|cheyyi|pettu|kottu)$""", RegexOption.IGNORE_CASE)
        teluguRegex1.find(trimmed)?.let { match ->
            val target = match.groupValues[1].trim()
            if (target.isNotBlank()) return target
        }

        val teluguRegex2 = Regex("""^(?:call|phone)\s*(?:cheyi|cheyyi|pettu|kottu)\s*(?:to\s+)?(.+?)(?:\s*(?:ki|ku))?$""", RegexOption.IGNORE_CASE)
        teluguRegex2.find(trimmed)?.let { match ->
            val target = match.groupValues[1].trim()
            if (target.isNotBlank()) return target
        }

        return null
    }

    /**
     * Dials or places a phone call directly.
     * If CALL_PHONE permission is granted, initiates direct call via ACTION_CALL.
     * Otherwise, opens system dialer pre-populated with ACTION_DIAL.
     */
    fun makeCall(context: Context, phoneNumber: String): Boolean {
        try {
            val raw = phoneNumber.trim()
            val normalized = ContactHelper.normalizePhoneNumber(raw)
            val dialNumber = if (normalized.matches(Regex("""^91\d{10}$"""))) {
                "+$normalized"
            } else if (raw.isNotBlank()) {
                raw
            } else {
                normalized
            }
            if (dialNumber.isBlank()) return false

            val hasCallPermission = ContextCompat.checkSelfPermission(
                context,
                Manifest.permission.CALL_PHONE
            ) == PackageManager.PERMISSION_GRANTED

            val action = if (hasCallPermission) Intent.ACTION_CALL else Intent.ACTION_DIAL
            val uri = Uri.parse("tel:${Uri.encode(dialNumber)}")

            val intent = Intent(action, uri).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            context.startActivity(intent)
            return true
        } catch (e: Exception) {
            Log.e(TAG, "[$TAG] Failed to make phone call", e)
            try {
                // Fallback to ACTION_DIAL if ACTION_CALL failed
                val uri = Uri.parse("tel:${Uri.encode(phoneNumber.trim())}")
                val intent = Intent(Intent.ACTION_DIAL, uri).apply {
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK
                }
                context.startActivity(intent)
                return true
            } catch (e2: Exception) {
                Log.e(TAG, "[$TAG] Dial fallback also failed", e2)
                return false
            }
        }
    }
}
