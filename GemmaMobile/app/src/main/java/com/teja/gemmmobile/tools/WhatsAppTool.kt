package com.teja.gemmmobile.tools

import android.content.Context
import com.teja.gemmmobile.assistant.ContactHelper
import com.teja.gemmmobile.assistant.WhatsAppAction
import com.teja.gemmmobile.assistant.WhatsAppActionHandler
import com.teja.gemmmobile.assistant.WhatsAppStatus

/**
 * On-device WhatsApp action tool.
 * Resolves contacts, composes natural messages, and generates an action card
 * strictly awaiting explicit user confirmation before any message is sent.
 */
class WhatsAppTool(
    private val context: Context
) : GemmaTool {

    override val name: String = "send_whatsapp"

    override val description: String =
        "Prepares a WhatsApp message to send to a contact or phone number. Always prompts the user for confirmation before sending."

    override val parametersJsonSchema: String = """
    {
      "type": "object",
      "properties": {
        "contact_name": {
          "type": "string",
          "description": "The recipient's name, nickname, or phone number (e.g. 'Manoj', 'Dad', '9542696946')."
        },
        "message": {
          "type": "string",
          "description": "The message text to send or the intent (e.g. 'Hey, are you free today?', 'happy birthday wishes')."
        }
      },
      "required": ["contact_name", "message"]
    }
    """.trimIndent()

    override suspend fun execute(arguments: Map<String, Any?>): ToolResult {
        val contactQuery = arguments["contact_name"] as? String ?: return ToolResult.failure("Missing 'contact_name'")
        val rawMessage = arguments["message"] as? String ?: return ToolResult.failure("Missing 'message'")

        val matches = ContactHelper.searchContact(context, contactQuery)

        if (matches.isEmpty()) {
            val resolvedMsg = WhatsAppActionHandler.resolveMessageBody(contactQuery, rawMessage)
            val action = WhatsAppAction(
                recipientName = contactQuery,
                messageText = resolvedMsg,
                rawIntent = rawMessage,
                matchedNumber = null,
                candidateContacts = emptyList(),
                status = WhatsAppStatus.NO_CONTACT_FOUND
            )
            return ToolResult.success(
                content = "I could not find \"$contactQuery\" in your contacts. Please verify the contact name or check permissions.",
                data = action
            )
        }

        val primaryMatch = matches.first()
        val resolvedBody = WhatsAppActionHandler.resolveMessageBody(primaryMatch.name, rawMessage)

        val action = WhatsAppAction(
            recipientName = primaryMatch.name,
            messageText = resolvedBody,
            rawIntent = rawMessage,
            matchedNumber = primaryMatch.phoneNumber,
            candidateContacts = matches,
            status = WhatsAppStatus.AWAITING_CONFIRMATION
        )

        val promptResponse = "Prepared WhatsApp message for **${primaryMatch.name}** (${primaryMatch.formattedNumber}):\n> \"$resolvedBody\"\n\nAwaiting user confirmation to send."
        return ToolResult.success(content = promptResponse, data = action)
    }
}
