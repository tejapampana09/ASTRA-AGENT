package com.teja.gemmmobile.tools

import com.teja.gemmmobile.search.SearchResult
import com.teja.gemmmobile.search.WebSearchClient
import kotlinx.coroutines.withTimeoutOrNull

/**
 * On-device live web search tool using WebSearchClient.
 */
class WebSearchTool(
    private val client: WebSearchClient = WebSearchClient()
) : GemmaTool {

    override val name: String = "web_search"

    override val description: String =
        "Search the live internet for recent events, facts, news, people, websites, URLs, and real-time information."

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
        val cleanQuery = client.sanitizeQuery(query)
        if (cleanQuery.isBlank()) return ToolResult.failure("Search query cannot be empty")

        val results = withTimeoutOrNull(9000L) {
            client.search(cleanQuery, maxResults = 8)
        } ?: emptyList()

        if (results.isEmpty()) {
            return ToolResult.success("No relevant web search results found for: \"$cleanQuery\"", data = emptyList<SearchResult>())
        }

        val formatted = buildString {
            appendLine("Web Search Results for \"$cleanQuery\":")
            results.forEachIndexed { index, res ->
                val cleanTitle = res.title.substringBefore("-").substringBefore("|").trim()
                appendLine("[${index + 1}] Title: $cleanTitle")
                appendLine("    URL: ${res.url}")
                appendLine("    Snippet: ${res.snippet.trim()}")
                appendLine()
            }
        }.trim()

        return ToolResult.success(formatted, data = results)
    }
}
