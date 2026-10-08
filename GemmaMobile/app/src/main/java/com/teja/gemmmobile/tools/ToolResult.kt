package com.teja.gemmmobile.tools

/**
 * Encapsulates the execution result of any tool invocation.
 */
data class ToolResult(
    val success: Boolean,
    val content: String,
    val error: String? = null,
    val data: Any? = null
) {
    companion object {
        fun success(content: String, data: Any? = null): ToolResult =
            ToolResult(success = true, content = content, error = null, data = data)

        fun failure(error: String, partialContent: String = ""): ToolResult =
            ToolResult(success = false, content = partialContent, error = error, data = null)
    }
}
