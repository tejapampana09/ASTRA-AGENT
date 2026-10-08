package com.teja.gemmmobile.tools

import com.teja.gemmmobile.search.SearchManager
import com.teja.gemmmobile.search.SearchResult
import kotlinx.coroutines.withTimeoutOrNull

/**
 * On-device live web search tool using SearchManager.
 * Enriches search results with verified readable content from top public webpages.
 */
class WebSearchTool(
    private val searchManager: SearchManager = SearchManager()
) : GemmaTool {

    override val name: String = "web_search"

    override val description: String =
        "Search the live internet for recent events, facts, news, people, websites, URLs, and real-time information, extracting readable webpage content."

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
        val query = arguments["query"] as? String ?: return ToolResult.failure("Missing required 'query' parameter")
        val cleanQuery = query.trim()
        if (cleanQuery.isBlank()) return ToolResult.failure("Search query cannot be empty")

        val results = withTimeoutOrNull(10000L) {
            searchManager.searchAndRead(cleanQuery, maxResults = 5)
        } ?: emptyList()

        if (results.isEmpty()) {
            return ToolResult.success("No relevant web search results found for: \"$cleanQuery\"", data = emptyList<SearchResult>())
        }

        val formatted = buildString {
            appendLine("WEB SEARCH RESULTS")
            appendLine()
            results.forEachIndexed { index, res ->
                val cleanTitle = res.title.substringBefore("-").substringBefore("|").trim()
                appendLine("[${index + 1}]")
                appendLine("Title: $cleanTitle")
                appendLine("URL: ${res.url}")
                appendLine("Search snippet: ${res.snippet.trim()}")
                if (res.fetchSucceeded && res.pageContent.isNotBlank()) {
                    appendLine("Page content:")
                    appendLine(res.pageContent.take(1500).trim())
                } else {
                    appendLine("Page content: Unavailable (rely on search snippet above)")
                }
                appendLine()
            }
        }.trim()

        return ToolResult.success(formatted, data = results.map { it.toSearchResult() })
    }
}
