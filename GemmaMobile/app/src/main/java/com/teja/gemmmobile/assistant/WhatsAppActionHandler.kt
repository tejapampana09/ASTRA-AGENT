package com.teja.gemmmobile.assistant

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.util.Log

private const val TAG = "WhatsAppHandler"

data class WhatsAppAction(
    val recipientName: String,
    val messageText: String,
    val rawIntent: String = "",
    val matchedNumber: String? = null,
    val candidateContacts: List<ContactMatch> = emptyList(),
    val status: WhatsAppStatus = WhatsAppStatus.AWAITING_CONFIRMATION
)

enum class WhatsAppStatus {
    IDLE,
    AWAITING_CONFIRMATION,
    CONFIRMED,
    SENDING,
    SENT_DIRECTLY,
    READY_TO_SEND,
    NO_CONTACT_FOUND,
    PERMISSION_NEEDED,
    CANCELLED
}

object WhatsAppActionHandler {

    /**
     * Intelligently resolves message intent into an appropriate, natural message body.
     * If the user gave a directive like "a greeting", "birthday wishes", "good morning", etc.,
     * this composes a warm, human-like message rather than sending literal intent words.
     */
    fun resolveMessageBody(recipientName: String, rawIntent: String): String {
        val clean = rawIntent.trim().trim('\'', '"')
        val lower = clean.lowercase()

        // 1. Generic greeting / wishes: "a greeting", "greeting", "wishes", "a warm greeting", "oka greeting", "say hi"
        val isGreeting = lower.matches(Regex("""^(?:a|an|the|oka)?\s*(?:warm\s+|friendly\s+|sweet\s+|nice\s+)?(?:greeting|greetings|wishes|greeting\s+message)\b.*"""))
                || lower in listOf("greeting", "greetings", "a greeting", "oka greeting", "wish", "wishes", "say hi", "greet him", "greet her")
        if (isGreeting) {
            return "Hey $recipientName, hope you're having a wonderful day! 😊✨"
        }

        // 2. Birthday wishes: "birthday wishes", "happy birthday", "a birthday wish"
        val isBirthday = lower.matches(Regex("""^(?:a|an|the|warm|heartiest)?\s*(?:birthday\s+(?:wish(?:es)?|greeting|message)|happy\s+birthday)\b.*"""))
        if (isBirthday) {
            return "Happy Birthday $recipientName! 🎂🎉 Wishing you an amazing year ahead filled with joy and success!"
        }

        // 3. Good morning
        val isMorning = lower.matches(Regex("""^(?:a|an)?\s*(?:good\s+morning|morning\s+wishes?)\b.*"""))
        if (isMorning) {
            return "Good morning $recipientName! ☀️ Wishing you a productive and great day ahead!"
        }

        // 4. Good night
        val isNight = lower.matches(Regex("""^(?:a|an)?\s*(?:good\s+night|night\s+wishes?|sweet\s+dreams)\b.*"""))
        if (isNight) {
            return "Good night $recipientName! 🌙 Have a peaceful sleep and sweet dreams."
        }

        // 5. Congratulations
        val isCongrats = lower.matches(Regex("""^(?:a|an|hearty)?\s*(?:congratulations|congrats|wishes\s+on\s+your\s+success)\b.*"""))
        if (isCongrats) {
            return "Congratulations $recipientName! 🎊👏 Really thrilled for you, wishing you continued success!"
        }

        // 6. Apology / Sorry
        val isApology = lower.matches(Regex("""^(?:an?|my)?\s*(?:apology|sorry|sorry\s+message)\b.*"""))
        if (isApology) {
            return "Hey $recipientName, I wanted to sincerely apologize for earlier. Hope you understand!"
        }

        // 7. Thank you
        val isThanks = lower.matches(Regex("""^(?:a\s+)?(?:thank\s+you|thanks|appreciation\s+message)\b.*"""))
        if (isThanks) {
            return "Hey $recipientName, thank you so much for your help and support! Really appreciate it! 🙏"
        }

        // 8. "that <message>" or "to <message>"
        if (lower.startsWith("that ")) {
            val extracted = clean.substring(5).trim()
            return "Hey $recipientName, $extracted"
        }
        if (lower.startsWith("to ")) {
            val extracted = clean.substring(3).trim()
            return "Hey $recipientName, please $extracted"
        }

        // 9. Short direct greetings
        if (lower in listOf("hi", "hello", "hey", "hii", "heyy")) {
            return "Hi $recipientName! 👋"
        }

        // Otherwise return clean verbatim message, capitalized nicely
        return clean.replaceFirstChar { if (it.isLowerCase()) it.titlecase() else it.toString() }
    }

    /**
     * Checks if a user prompt is asking to send a WhatsApp message and extracts recipient & raw intent.
     */
    fun parseWhatsAppIntent(prompt: String): Pair<String, String>? {
        val trimmed = prompt.trim()

        // 1. Regex: "send <message> to <contact> in/on whatsapp"
        // e.g. "send a greeting to suhas in whatsapp", "send hi to manoj on whatsapp"
        val pattern1 = Regex("""(?:please\s+)?send\s+(.+?)\s+to\s+([a-zA-Z0-9_\s]+?)\s+(?:in|on|through|via)\s+whatsapp""", RegexOption.IGNORE_CASE)
        pattern1.find(trimmed)?.let { match ->
            val message = match.groupValues[1].trim('\'', '"', ' ')
            val contact = match.groupValues[2].trim()
            if (contact.isNotBlank() && message.isNotBlank()) return Pair(contact, message)
        }

        // 2. Regex: "send <contact> <message> on/in whatsapp"
        // e.g. "send suhas a greeting on whatsapp", "send manoj birthday wishes in whatsapp"
        val pattern2a = Regex("""(?:please\s+)?send\s+([a-zA-Z0-9_]+)\s+(.+?)\s+(?:in|on|through|via)\s+whatsapp""", RegexOption.IGNORE_CASE)
        pattern2a.find(trimmed)?.let { match ->
            val contact = match.groupValues[1].trim()
            val message = match.groupValues[2].trim('\'', '"', ' ')
            if (contact.isNotBlank() && message.isNotBlank() && !contact.equals("to", ignoreCase = true)) {
                return Pair(contact, message)
            }
        }

        // 3. Regex: "whatsapp <contact> <message>" or "whatsapp to <contact> <message>"
        // e.g. "whatsapp manoj hi", "whatsapp to manoj I am on the way"
        val pattern2 = Regex("""whatsapp\s+(?:to\s+)?([a-zA-Z0-9_]+)\s+['"]?([^'"]+)['"]?""", RegexOption.IGNORE_CASE)
        pattern2.find(trimmed)?.let { match ->
            val contact = match.groupValues[1].trim()
            val message = match.groupValues[2].trim()
            if (contact.isNotBlank() && message.isNotBlank() && !contact.equals("message", ignoreCase = true)) {
                return Pair(contact, message)
            }
        }

        // 4. Regex: "tell <contact> on whatsapp that/to <message>"
        val pattern3 = Regex("""(?:please\s+)?tell\s+([a-zA-Z0-9_]+)\s+(?:on|in)\s+whatsapp\s+(?:that|to)?\s*(.+)""", RegexOption.IGNORE_CASE)
        pattern3.find(trimmed)?.let { match ->
            val contact = match.groupValues[1].trim()
            val message = match.groupValues[2].trim()
            if (contact.isNotBlank() && message.isNotBlank()) return Pair(contact, message)
        }

        // 5. Telugu patterns with whatsapp:
        // "<contact> ki whatsapp lo <message> pettu" e.g. "suhas ki whatsapp lo greeting pettu", "manoj ki whatsapp lo hi pettu"
        val teluguPattern1 = Regex("""([a-zA-Z0-9_]+)\s*(?:ki|ku)?\s+whatsapp\s+lo\s+(.+?)\s*(?:pettu|cheppu|send\s*cheyi|pampinchu)""", RegexOption.IGNORE_CASE)
        teluguPattern1.find(trimmed)?.let { match ->
            val contact = match.groupValues[1].trim()
            val message = match.groupValues[2].trim()
            if (contact.isNotBlank() && message.isNotBlank()) return Pair(contact, message)
        }

        // "whatsapp lo <contact> ki <message> pettu"
        val teluguPattern2 = Regex("""whatsapp\s+lo\s+([a-zA-Z0-9_]+)\s*(?:ki|ku)?\s+(.+?)\s*(?:pettu|cheppu|send\s*cheyi|pampinchu)""", RegexOption.IGNORE_CASE)
        teluguPattern2.find(trimmed)?.let { match ->
            val contact = match.groupValues[1].trim()
            val message = match.groupValues[2].trim()
            if (contact.isNotBlank() && message.isNotBlank()) return Pair(contact, message)
        }

        // 6. Short natural form: "send <message> to <contact>"
        // e.g. "send hi to teja", "send hello to manoj"
        val pattern4 = Regex("""^(?:please\s+)?send\s+(.+?)\s+to\s+([a-zA-Z0-9_]+)$""", RegexOption.IGNORE_CASE)
        pattern4.find(trimmed)?.let { match ->
            val message = match.groupValues[1].trim('\'', '"', ' ')
            val contact = match.groupValues[2].trim()
            if (contact.isNotBlank() && message.isNotBlank()) return Pair(contact, message)
        }

        // 7. Short Telugu form: "<contact> ki <message> pettu" e.g. "teja ki hi pettu"
        val teluguPattern3 = Regex("""^([a-zA-Z0-9_]+)\s*(?:ki|ku)\s+(.+?)\s*(?:pettu|cheppu|send\s*cheyi|pampinchu)$""", RegexOption.IGNORE_CASE)
        teluguPattern3.find(trimmed)?.let { match ->
            val contact = match.groupValues[1].trim()
            val message = match.groupValues[2].trim()
            if (contact.isNotBlank() && message.isNotBlank()) return Pair(contact, message)
        }

        return null
    }

    /**
     * Executes the WhatsApp action directly using contact number and accessibility auto-send.
     */
    fun sendWhatsAppDirect(
        context: Context,
        phoneNumber: String,
        message: String,
        autoSend: Boolean = true
    ): Boolean {
        try {
            val normalized = ContactHelper.normalizePhoneNumber(phoneNumber)
            if (normalized.isBlank()) return false

            val encodedMsg = Uri.encode(message)
            val uri = Uri.parse("https://api.whatsapp.com/send?phone=$normalized&text=$encodedMsg")

            if (autoSend && GemmaAccessibilityService.isAccessibilityEnabled(context)) {
                GemmaAccessibilityService.armAutoSend(normalized)
            }

            val intent = Intent(Intent.ACTION_VIEW, uri).apply {
                setPackage("com.whatsapp")
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }

            // Fallback to general intent if WhatsApp package is business or unpinned
            try {
                context.startActivity(intent)
            } catch (_: Exception) {
                intent.setPackage(null)
                context.startActivity(intent)
            }
            return true
        } catch (e: Exception) {
            Log.e(TAG, "[$TAG] Failed to send WhatsApp message", e)
            return false
        }
    }
}
