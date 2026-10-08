package com.teja.gemmmobile.tools

import com.teja.gemmmobile.search.SearchConfig
import com.teja.gemmmobile.search.SearchManager
import com.teja.gemmmobile.search.SearchResult
import kotlinx.coroutines.withTimeoutOrNull

/**
 * On-device live web search tool using SearchManager.
 * Enriches search results with verified readable content from top public webpages.
 * Enforces strict untrusted data boundaries to mitigate prompt injection.
 */
class WebSearchTool(
    private val searchManager: SearchManager = SearchManager()
) : GemmaTool {

    override val name: String = "web_search"

    override val description: String =
        "Search the live internet for recent events, facts, news, websites, articles, and real-time text information. " +
        "Call this when the user asks about current facts, recent events, websites, or questions needing live web evidence. " +
        "DO NOT use this tool for images or photos; use 'image_search' instead for visual media."

    override val parametersJsonSchema: String = """
    {
      "type": "object",
      "properties": {
        "query": {
          "type": "string",
          "description": "The specific query to search the web for."
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

        val results = withTimeoutOrNull(10000L) {
            searchManager.searchAndRead(query, maxResults = SearchConfig.DEFAULT_MAX_SEARCH_RESULTS)
        } ?: emptyList()

        if (results.isEmpty()) {
            return ToolResult.success("No relevant web search results found for: \"$query\".", data = emptyList<SearchResult>())
        }

        val formatted = searchManager.formatGemmaWebContext(results)
        return ToolResult.success(formatted, data = results.map { it.toSearchResult() })
    }
}
