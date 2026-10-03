package com.teja.gemmmobile.search

import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

private const val TAG = "WebSearchClient"

/**
 * Clean data model for a single web search snippet.
 */
data class SearchResult(
    val title: String,
    val url: String,
    val snippet: String
)

/**
 * Fast, lightweight on-device web search client using DuckDuckGo Lite.
 * Requires 0 API keys and runs on background IO dispatcher.
 */
class WebSearchClient {

    suspend fun search(query: String, maxResults: Int = 3): List<SearchResult> = withContext(Dispatchers.IO) {
        if (query.isBlank()) return@withContext emptyList()

        try {
            Log.d(TAG, "[$TAG] Querying live web search for: $query")
            val endpoint = URL("https://lite.duckduckgo.com/lite/")
            val conn = endpoint.openConnection() as HttpURLConnection
            conn.requestMethod = "POST"
            conn.connectTimeout = 3000
            conn.readTimeout = 3000
            conn.doOutput = true
            conn.setRequestProperty("User-Agent", "Mozilla/5.0 (Linux; Android 14; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36")
            conn.setRequestProperty("Content-Type", "application/x-www-form-urlencoded")
            conn.setRequestProperty("Accept", "text/html,application/xhtml+xml")

            val postData = "q=" + URLEncoder.encode(query, "UTF-8")
            OutputStreamWriter(conn.outputStream, "UTF-8").use { writer ->
                writer.write(postData)
                writer.flush()
            }

            val responseCode = conn.responseCode
            if (responseCode != 200) {
                Log.w(TAG, "[$TAG] DuckDuckGo Lite returned HTTP $responseCode")
                return@withContext emptyList()
            }

            val html = BufferedReader(InputStreamReader(conn.inputStream, "UTF-8")).use { reader ->
                reader.readText()
            }

            val results = parseSearchResults(html, maxResults)
            Log.d(TAG, "[$TAG] Successfully retrieved ${results.size} search snippets")
            results
        } catch (t: Throwable) {
            Log.e(TAG, "[$TAG] Web search failed", t)
            emptyList()
        }
    }

    private fun parseSearchResults(html: String, maxResults: Int): List<SearchResult> {
        val results = mutableListOf<SearchResult>()

        val tagRegex = Regex("""<a\s+([^>]*class=['"][^'"]*result-link[^'"]*['"][^>]*)>(.*?)</a>""", RegexOption.DOT_MATCHES_ALL)
        val snippetRegex = Regex("""<td[^>]*class=['"][^'"]*result-snippet[^'"]*['"][^>]*>(.*?)</td>""", RegexOption.DOT_MATCHES_ALL)
        val hrefRegex = Regex("""href=['"]([^'"]+)['"]""")

        val linkMatches = tagRegex.findAll(html).toList()
        val snippetMatches = snippetRegex.findAll(html).toList()

        val count = minOf(linkMatches.size, snippetMatches.size, maxResults)
        for (i in 0 until count) {
            val attrs = linkMatches[i].groupValues[1]
            val rawTitle = linkMatches[i].groupValues[2]
            val hrefMatch = hrefRegex.find(attrs)
            val url = hrefMatch?.groupValues?.get(1)?.let { cleanHtml(it) } ?: ""
            val title = cleanHtml(rawTitle)
            val snippet = cleanHtml(snippetMatches[i].groupValues[1])

            if (title.isNotBlank() && snippet.isNotBlank()) {
                results.add(SearchResult(title = title, url = url, snippet = snippet))
            }
        }

        return results
    }

    private fun cleanHtml(raw: String): String {
        return raw.replace(Regex("<[^>]+>"), "")
            .replace("&#x27;", "'")
            .replace("&quot;", "\"")
            .replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&nbsp;", " ")
            .trim()
    }
}
