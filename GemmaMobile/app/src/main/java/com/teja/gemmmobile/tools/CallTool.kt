package com.teja.gemmmobile.tools

import android.content.Context
import com.teja.gemmmobile.assistant.CallAction
import com.teja.gemmmobile.assistant.CallStatus
import com.teja.gemmmobile.assistant.ContactHelper

/**
 * On-device phone call action tool.
 * Resolves contacts, validates phone numbers, and generates a call action card
 * strictly awaiting explicit user confirmation before placing or dialing any call.
 */
class CallTool(
    private val context: Context
) : GemmaTool {

    override val name: String = "make_call"

    override val description: String =
        "Prepares a phone call to a contact or phone number. Always prompts the user for confirmation before dialing."

    override val parametersJsonSchema: String = """
    {
      "type": "object",
      "properties": {
        "contact_name": {
          "type": "string",
          "description": "The person's name or phone number to call (e.g. 'Manoj', 'Dad', '9542696946')."
        }
      },
      "required": ["contact_name"]
    }
    """.trimIndent()

    override suspend fun execute(arguments: Map<String, Any?>): ToolResult {
        val query = arguments["contact_name"] as? String ?: return ToolResult.failure("Missing 'contact_name'")
        val cleanQuery = query.trim()

        // Check if query is already a phone number
        val normalized = ContactHelper.normalizePhoneNumber(cleanQuery)
        if (normalized.length >= 7 && normalized.all { it.isDigit() || it == '+' }) {
            val action = CallAction(
                recipientName = cleanQuery,
                matchedNumber = normalized,
                candidateContacts = emptyList(),
                status = CallStatus.AWAITING_CONFIRMATION
            )
            return ToolResult.success(
                content = "Prepared phone call to **$cleanQuery**.\nAwaiting user confirmation to dial.",
                data = action
            )
        }

        val matches = ContactHelper.searchContact(context, cleanQuery)
        if (matches.isEmpty()) {
            val action = CallAction(
                recipientName = cleanQuery,
                matchedNumber = null,
                candidateContacts = emptyList(),
                status = CallStatus.NO_CONTACT_FOUND
            )
            return ToolResult.success(
                content = "I could not find \"$cleanQuery\" in your contacts. Please verify the contact name or check permissions.",
                data = action
            )
        }

        val primaryMatch = matches.first()
        val action = CallAction(
            recipientName = primaryMatch.name,
            matchedNumber = primaryMatch.phoneNumber,
            candidateContacts = matches,
            status = CallStatus.AWAITING_CONFIRMATION
        )

        return ToolResult.success(
            content = "Found **${primaryMatch.name}** (${primaryMatch.formattedNumber}).\nAwaiting user confirmation to place the call.",
            data = action
        )
    }
}
