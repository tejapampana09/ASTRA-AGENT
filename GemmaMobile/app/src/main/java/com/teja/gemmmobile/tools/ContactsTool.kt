package com.teja.gemmmobile.tools

import android.content.Context
import com.teja.gemmmobile.assistant.ContactHelper
import com.teja.gemmmobile.assistant.ContactMatch

/**
 * On-device contacts search tool.
 */
class ContactsTool(
    private val context: Context
) : GemmaTool {

    override val name: String = "search_contacts"

    override val description: String =
        "Search the user's address book and contacts by name or nickname to retrieve phone numbers."

    override val parametersJsonSchema: String = """
    {
      "type": "object",
      "properties": {
        "name": {
          "type": "string",
          "description": "The name or nickname of the contact to find (e.g. 'Manoj', 'Dad', 'Teja')."
        }
      },
      "required": ["name"]
    }
    """.trimIndent()

    override suspend fun execute(arguments: Map<String, Any?>): ToolResult {
        val nameQuery = arguments["name"] as? String ?: return ToolResult.failure("Missing required 'name' parameter")
        val matches = ContactHelper.searchContact(context, nameQuery)

        if (matches.isEmpty()) {
            return ToolResult.success("No contacts found matching \"$nameQuery\".", data = emptyList<ContactMatch>())
        }

        val formatted = buildString {
            appendLine("Found ${matches.size} contact match(es) for \"$nameQuery\":")
            matches.take(5).forEachIndexed { idx, match ->
                appendLine("[${idx + 1}] Name: ${match.name}, Phone: ${match.formattedNumber}")
            }
        }.trim()

        return ToolResult.success(formatted, data = matches)
    }
}
