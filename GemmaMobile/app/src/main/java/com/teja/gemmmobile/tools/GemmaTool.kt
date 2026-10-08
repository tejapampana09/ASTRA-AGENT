package com.teja.gemmmobile.tools

/**
 * Representation of a structured tool invocation requested by the model.
 */
data class ToolCallRequest(
    val name: String,
    val arguments: Map<String, Any?> = emptyMap()
)

/**
 * Common contract for all on-device tools executable by Gemma.
 */
interface GemmaTool {
    /**
     * Unique identifier of the tool (e.g. "web_search", "image_search", "save_memory", "extract_document").
     */
    val name: String

    /**
     * Human-readable description explaining when and how the model should call this tool.
     */
    val description: String

    /**
     * JSON Schema representation of parameters expected by the tool.
     */
    val parametersJsonSchema: String

    /**
     * Executes the tool with the provided arguments safely.
     */
    suspend fun execute(arguments: Map<String, Any?>): ToolResult
}
