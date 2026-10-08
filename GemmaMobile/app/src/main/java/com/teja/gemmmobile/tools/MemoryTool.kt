package com.teja.gemmmobile.tools

import com.teja.gemmmobile.memory.MemoryManager

/**
 * On-device long-term memory management tool.
 */
class MemoryTool(
    private val memoryManager: MemoryManager
) : GemmaTool {

    override val name: String = "manage_memory"

    override val description: String =
        "Saves important persistent facts, preferences, or personal details about the user to long-term memory, or retrieves existing memories."

    override val parametersJsonSchema: String = """
    {
      "type": "object",
      "properties": {
        "action": {
          "type": "string",
          "enum": ["save", "get"],
          "description": "'save' to record a new fact, or 'get' to inspect current saved memories."
        },
        "fact": {
          "type": "string",
          "description": "The exact fact or preference to remember (required when action is 'save')."
        }
      },
      "required": ["action"]
    }
    """.trimIndent()

    override suspend fun execute(arguments: Map<String, Any?>): ToolResult {
        val action = (arguments["action"] as? String)?.lowercase() ?: "get"

        return when (action) {
            "save" -> {
                val fact = arguments["fact"] as? String
                if (fact.isNullOrBlank()) {
                    return ToolResult.failure("Missing 'fact' parameter for save action")
                }
                memoryManager.addMemory(fact.trim())
                ToolResult.success("Successfully remembered: \"${fact.trim()}\"")
            }
            "get" -> {
                val memories = memoryManager.memories.value
                if (memories.isEmpty()) {
                    ToolResult.success("No saved memories found.")
                } else {
                    val formatted = memories.joinToString("\n") { "• ${it.fact}" }
                    ToolResult.success("Current User Memories:\n$formatted", data = memories)
                }
            }
            else -> ToolResult.failure("Unsupported action: '$action'. Use 'save' or 'get'.")
        }
    }
}
