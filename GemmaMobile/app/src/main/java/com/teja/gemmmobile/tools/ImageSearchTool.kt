package com.teja.gemmmobile.tools

import com.teja.gemmmobile.search.SearchConfig
import com.teja.gemmmobile.search.SearchImage
import com.teja.gemmmobile.search.SearchManager
import kotlinx.coroutines.withTimeoutOrNull

/**
 * First-class Gemma tool for searching high-quality on-device web images, diagrams, and photos.
 * Returns structured SearchImage items rendered in the in-app carousel and preview dialog.
 */
class ImageSearchTool(
    private val searchManager: SearchManager = SearchManager()
) : GemmaTool {

    override val name: String = "image_search"

    override val description: String =
        "Search the web for visual images, photographs, architecture diagrams, charts, and illustrations. " +
        "Call this tool when the user asks to see, find, or show images, photos, architecture diagrams, or visual examples. " +
        "DO NOT call this for text facts or news; call 'web_search' instead for web articles and facts."

    override val parametersJsonSchema: String = """
    {
      "type": "object",
      "properties": {
        "query": {
          "type": "string",
          "description": "The visual search query (e.g. 'VAE architecture diagram', '8086 pinout', 'James Webb telescope')."
        },
        "max_results": {
          "type": "integer",
          "description": "Number of images to retrieve (1 to 8, default 5)."
        }
      },
      "required": ["query"]
    }
    """.trimIndent()

    override suspend fun execute(arguments: Map<String, Any?>): ToolResult {
        val query = (arguments["query"] as? String)?.trim()
        if (query.isNullOrBlank()) {
            return ToolResult.failure("Invalid arguments: 'query' is required and cannot be blank.")
        }

        if (query.length > SearchConfig.MAX_TOOL_ARG_STRING_CHARS) {
            return ToolResult.failure("Invalid arguments: 'query' exceeds maximum length limit of ${SearchConfig.MAX_TOOL_ARG_STRING_CHARS} characters.")
        }

        val maxResults = when (val mr = arguments["max_results"]) {
            is Number -> mr.toInt().coerceIn(1, 8)
            is String -> mr.toIntOrNull()?.coerceIn(1, 8) ?: 5
            else -> 5
        }

        val images = withTimeoutOrNull(8000L) {
            searchManager.searchImages(query = query, maxImages = maxResults)
        } ?: emptyList()

        if (images.isEmpty()) {
            return ToolResult.success("No images found for query: \"$query\".", data = emptyList<SearchImage>())
        }

        val formattedText = buildString {
            appendLine("FOUND ${images.size} IMAGES FOR: \"$query\"")
            images.forEachIndexed { idx, img ->
                appendLine("[${idx + 1}] Title: ${img.title}")
                appendLine("Image URL: ${img.imageUrl}")
                appendLine("Source URL: ${img.sourceUrl}")
                appendLine("Domain: ${img.sourceDomain}")
                appendLine()
            }
        }.trim()

        return ToolResult.success(formattedText, data = images)
    }
}
