package com.teja.gemmmobile.search

import androidx.compose.runtime.Immutable
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.withContext
import com.google.gson.JsonParser
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLDecoder
import java.net.URLEncoder

private const val TAG = "WebSearchClient"

/**
 * Clean data model for a single web search snippet.
 */
@Immutable
data class SearchResult(
    val title: String,
    val url: String,
    val snippet: String
)

/**
 * Fast, robust on-device web search client modeled after ChatGPT search.
 * Uses DuckDuckGo Lite (POST) and Wikipedia API concurrently to get rich,
 * unblocked results across the entire web (Wikipedia, IMDb, news, profiles, official sites).
 * Falls back to DuckDuckGo HTML and Bing if needed.
 * Zero API keys required.
 */
open class WebSearchClient {

    /**
     * Recursively and iteratively sanitizes raw user query into concise keywords for search engines.
     * Strips nested conversational commands (e.g., "search who is ...", "tell me about ...", Telugu suffixes).
     */
    fun sanitizeQuery(raw: String): String {
        var query = raw.trim()

        val prefixes = listOf(
            "can you please search the web and give product links for ",
            "can you please search the web and give product links ",
            "can you please search the web and give links for ",
            "can you please search the web and give links ",
            "can you please search web and give product links for ",
            "can you please search web and give product links ",
            "can you please search web and give links for ",
            "can you please search web and give links ",
            "can you please search web and give ",
            "can you please search web and ",
            "can you please search the web and ",
            "can you please search the web for ",
            "can you please search web for ",
            "can you please search for ",
            "can you please search ",
            "can you search the web and give product links ",
            "can you search web and give product links ",
            "can you search web and give links ",
            "can you search web and ",
            "can you search the web and ",
            "can you search the web for ",
            "can you search web for ",
            "can you search for ",
            "can you search ",
            "please search the web and give product links ",
            "please search web and give product links ",
            "please search web and give links ",
            "please search web and give ",
            "please search web and ",
            "please search the web and ",
            "please search the web for ",
            "please search web for ",
            "please search for ",
            "please search ",
            "search the web and give product links ",
            "search web and give product links ",
            "search web and give links ",
            "search web and give ",
            "search web and ",
            "search the web and ",
            "search the web for ",
            "search the web ",
            "search web for ",
            "search web ",
            "browse the web for ", "browse the web ", "browse web for ", "browse web ", "browse for ", "browse ",
            "google search for ", "google search ", "google for ", "google ",
            "look up on the web for ", "look up on web for ", "look up for ", "look up ",
            "find information about ", "find information on ", "find info about ", "find info on ",
            "find out about ", "find out ", "find for ", "find ",
            "give product links for ", "give product links ", "give links for ", "give links ", "give options for ", "give options ",
            "web and give product links for ", "web and give product links ", "web and give links ", "web and ",
            "tell me who is ", "tell me who was ", "tell me what is ", "tell me what was ", "tell me about ", "tell me ",
            "search for ", "search ",
            "who is ", "who was ", "who are ", "who were ",
            "what is ", "what was ", "what are ", "what were ",
            "where is ", "where was ", "where are ",
            "when is ", "when was ", "when did ",
            "why is ", "why did ", "how does ", "how to ",
            "information about ", "info about ", "details about ", "details of "
        )

        val teluguPrefixes = listOf(
            "naaku ", "dayachesi ", "konchem ", "asalu ",
            "web search chesi ", "net lo chusi ", "chusi cheppu ", "links ivvu "
        )

        val teluguSuffixes = listOf(
            " gurinchi vivarinchu", " gurinchi cheppu", " gurinchi telupu", " gurinchi",
            " vivarana cheppu", " vivarana", " cheppandi", " cheppu", " telupandi", " telupu",
            " ante enti", " enti", " telusu", " telusaa",
            " in telugu", " telugu lo", " please", " explain"
        )

        var changed = true
        var passes = 0
        while (changed && passes < 10) {
            changed = false
            passes++
            val trimmed = query.trim()

            for (p in prefixes) {
                if (trimmed.startsWith(p, ignoreCase = true)) {
                    val candidate = trimmed.substring(p.length).trim()
                    if (candidate.isNotBlank() && candidate.length >= 2) {
                        query = candidate
                        changed = true
                        break
                    }
                }
            }

            if (!changed) {
                for (tp in teluguPrefixes) {
                    if (trimmed.startsWith(tp, ignoreCase = true)) {
                        val candidate = trimmed.substring(tp.length).trim()
                        if (candidate.isNotBlank() && candidate.length >= 2) {
                            query = candidate
                            changed = true
                            break
                        }
                    }
                }
            }

            if (!changed) {
                for (s in teluguSuffixes) {
                    if (trimmed.endsWith(s, ignoreCase = true)) {
                        val candidate = trimmed.dropLast(s.length).trim()
                        if (candidate.isNotBlank() && candidate.length >= 2) {
                            query = candidate
                            changed = true
                            break
                        }
                    }
                }
            }
        }

        // Strip trailing punctuation like '?', '.', '!', quotes, commas
        query = query.trim('?', '.', '!', ',', '"', '\'', ':', ';', ' ')
        return query.ifBlank { raw.trim() }
    }

    /**
     * Determines whether a query string is too generic or conversational to search alone.
     */
    fun isGenericQuery(query: String): Boolean {
        val q = query.lowercase().trim()
        val genericTerms = setOf(
            "", "product links", "links", "products", "options", "it", "them", "this", "these",
            "sites", "stores", "web", "online", "details", "info", "recommendations", "suggestions"
        )
        return q in genericTerms || q.length < 3
    }

    /**
     * Executes broad web search across DuckDuckGo Lite, Bing Web Search, and Wikipedia API in parallel.
     */
    open suspend fun search(query: String, maxResults: Int = 10): List<SearchResult> = withContext(Dispatchers.IO) {
        val clean = sanitizeQuery(query)
        if (clean.isBlank()) return@withContext emptyList()

        try {
            Log.d(TAG, "[$TAG] Initiating broad parallel web search for: '$clean' (raw: '$query')")

            // Concurrently query DuckDuckGo Lite, Bing Web Search, and Wikipedia API in parallel
            val (ddgCandidates, bingCandidates, wikiCandidates) = coroutineScope {
                val ddgDeferred = async {
                    try { fetchDuckDuckGoLite(clean, maxResults * 2) } catch (_: Exception) { emptyList() }
                }
                val bingDeferred = async {
                    try { fetchBingWeb(clean, maxResults * 2) } catch (_: Exception) { emptyList() }
                }
                val wikiDeferred = async {
                    try { fetchWikipedia(clean, 3) } catch (_: Exception) { emptyList() }
                }
                Triple(ddgDeferred.await(), bingDeferred.await(), wikiDeferred.await())
            }

            val combined = mutableListOf<SearchResult>()
            combined.addAll(wikiCandidates)
            combined.addAll(ddgCandidates)
            combined.addAll(bingCandidates)

            // If primary engines were empty, fall back to DDG HTML
            if (combined.isEmpty()) {
                Log.d(TAG, "[$TAG] Primary engines empty, trying DDG HTML fallback")
                val ddgHtml = fetchDuckDuckGoHtml(clean, maxResults)
                combined.addAll(ddgHtml)
            }

            if (combined.isEmpty()) {
                Log.w(TAG, "[$TAG] All search providers returned 0 results for: '$clean'")
                return@withContext emptyList()
            }

            // Rank candidates by query relevance & domain diversity
            val ranked = rankByRelevance(combined, clean, maxResults)
            Log.d(TAG, "[$TAG] Curated ${ranked.size} broad web results for '$clean'")
            return@withContext ranked
        } catch (t: Throwable) {
            Log.e(TAG, "[$TAG] Search error", t)
            emptyList()
        }
    }

    /**
     * Queries Wikipedia Search API directly (50ms, zero rate limits, high encyclopedic authority).
     */
    fun fetchWikipedia(query: String, maxResults: Int = 3): List<SearchResult> {
        return try {
            val encodedQuery = URLEncoder.encode(query, "UTF-8")
            val endpoint = URL("https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch=$encodedQuery&format=json&utf8=1&srlimit=$maxResults")
            val conn = endpoint.openConnection() as HttpURLConnection
            conn.requestMethod = "GET"
            conn.connectTimeout = 3000
            conn.readTimeout = 3000
            conn.setRequestProperty("User-Agent", "GemmaMobile/1.0 (Android AI Assistant)")
            conn.setRequestProperty("Accept", "application/json")

            if (conn.responseCode == 200) {
                val json = BufferedReader(InputStreamReader(conn.inputStream, "UTF-8")).use { it.readText() }
                val root = JsonParser.parseString(json).asJsonObject
                val searchArray = root.getAsJsonObject("query")?.getAsJsonArray("search") ?: return emptyList()

                val results = mutableListOf<SearchResult>()
                for (elem in searchArray) {
                    val obj = elem.asJsonObject
                    val rawTitle = obj.get("title")?.asString ?: continue
                    val rawSnippet = obj.get("snippet")?.asString ?: ""
                    val cleanSnippet = cleanHtml(rawSnippet)
                    val pageUrl = "https://en.wikipedia.org/wiki/" + URLEncoder.encode(rawTitle.replace(" ", "_"), "UTF-8")

                    results.add(
                        SearchResult(
                            title = "$rawTitle - Wikipedia",
                            url = pageUrl,
                            snippet = cleanSnippet.ifBlank { rawTitle }
                        )
                    )
                }
                results
            } else {
                emptyList()
            }
        } catch (e: Exception) {
            Log.d(TAG, "[$TAG] Wikipedia search skipped: ${e.message}")
            emptyList()
        }
    }

    /**
     * DuckDuckGo Lite search endpoint: https://lite.duckduckgo.com/lite/
     * Uses POST, which bypasses duck CAPTCHAs and returns broad web results (Wikipedia, IMDb, news, blogs).
     */
    fun fetchDuckDuckGoLite(query: String, maxResults: Int): List<SearchResult> {
        return try {
            val endpoint = URL("https://lite.duckduckgo.com/lite/")
            val conn = endpoint.openConnection() as HttpURLConnection
            conn.requestMethod = "POST"
            conn.connectTimeout = 4500
            conn.readTimeout = 4500
            conn.doOutput = true
            conn.setRequestProperty("User-Agent", "Mozilla/5.0 (Linux; Android 14; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36")
            conn.setRequestProperty("Content-Type", "application/x-www-form-urlencoded")
            conn.setRequestProperty("Accept", "text/html,application/xhtml+xml")

            val postData = "q=" + URLEncoder.encode(query, "UTF-8")
            OutputStreamWriter(conn.outputStream, "UTF-8").use { writer ->
                writer.write(postData)
                writer.flush()
            }

            if (conn.responseCode == 200) {
                val html = BufferedReader(InputStreamReader(conn.inputStream, "UTF-8")).use { it.readText() }
                parseDdgLite(html, maxResults)
            } else {
                emptyList()
            }
        } catch (e: Exception) {
            Log.w(TAG, "[$TAG] DDG Lite query failed for '$query'", e)
            emptyList()
        }
    }

    fun parseDdgLite(html: String, maxResults: Int): List<SearchResult> {
        val results = mutableListOf<SearchResult>()
        val liteTagRegex = Regex("""<a\s+([^>]*class=['"][^'"]*result-link[^'"]*['"][^>]*)>(.*?)</a>""", RegexOption.DOT_MATCHES_ALL)
        val liteSnippetRegex = Regex("""<td[^>]*class=['"][^'"]*result-snippet[^'"]*['"][^>]*>(.*?)</td>""", RegexOption.DOT_MATCHES_ALL)
        val hrefRegex = Regex("""href=['"]([^'"]+)['"]""")

        val liteLinks = liteTagRegex.findAll(html).toList()
        val liteSnippets = liteSnippetRegex.findAll(html).toList()

        val count = minOf(liteLinks.size, maxResults)
        for (i in 0 until count) {
            val attrs = liteLinks[i].groupValues[1]
            val rawTitle = liteLinks[i].groupValues[2]
            val hrefMatch = hrefRegex.find(attrs)
            val rawUrl = hrefMatch?.groupValues?.get(1)?.let { cleanHtml(it) } ?: ""
            val url = cleanUrl(rawUrl)
            val title = cleanHtml(rawTitle)
            val snippet = if (i < liteSnippets.size) cleanSnippetText(liteSnippets[i].groupValues[1]) else ""

            if (title.isNotBlank() && url.isNotBlank() && url.startsWith("http")) {
                results.add(SearchResult(title = title, url = url, snippet = snippet.ifBlank { title }))
            }
        }
        return results
    }

    /**
     * DuckDuckGo HTML search endpoint (fallback).
     */
    fun fetchDuckDuckGoHtml(query: String, maxResults: Int): List<SearchResult> {
        return try {
            val endpoint = URL("https://html.duckduckgo.com/html/?q=" + URLEncoder.encode(query, "UTF-8"))
            val conn = endpoint.openConnection() as HttpURLConnection
            conn.requestMethod = "GET"
            conn.connectTimeout = 4000
            conn.readTimeout = 4000
            conn.setRequestProperty("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
            conn.setRequestProperty("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
            conn.setRequestProperty("Accept-Language", "en-US,en;q=0.9")

            if (conn.responseCode == 200) {
                val html = BufferedReader(InputStreamReader(conn.inputStream, "UTF-8")).use { it.readText() }
                parseDdgHtml(html, maxResults)
            } else {
                emptyList()
            }
        } catch (e: Exception) {
            Log.w(TAG, "[$TAG] DDG HTML query failed for '$query'", e)
            emptyList()
        }
    }

    private fun parseDdgHtml(html: String, maxResults: Int): List<SearchResult> {
        val results = mutableListOf<SearchResult>()
        val linkRegex = Regex("""<a\s+[^>]*class=['"][^'"]*result__a[^'"]*['"][^>]*href=['"]([^'"]+)['"][^>]*>(.*?)</a>""", RegexOption.DOT_MATCHES_ALL)
        val snippetRegex = Regex("""<a\s+[^>]*class=['"][^'"]*(?:result__snippet|snippet)[^'"]*['"][^>]*>(.*?)</a>""", RegexOption.DOT_MATCHES_ALL)

        val links = linkRegex.findAll(html).toList()
        val snippets = snippetRegex.findAll(html).toList()

        val count = minOf(links.size, maxResults)
        for (i in 0 until count) {
            val rawUrl = links[i].groupValues[1]
            val rawTitle = links[i].groupValues[2]
            val url = cleanUrl(cleanHtml(rawUrl))
            val title = cleanHtml(rawTitle)
            val snippet = if (i < snippets.size) cleanSnippetText(snippets[i].groupValues[1]) else ""

            if (title.isNotBlank() && url.isNotBlank() && url.startsWith("http")) {
                results.add(SearchResult(title = title, url = url, snippet = snippet.ifBlank { title }))
            }
        }
        return results
    }

    /**
     * Bing Web Search endpoint (tertiary fallback).
     */
    fun fetchBingWeb(query: String, maxResults: Int): List<SearchResult> {
        return try {
            val endpoint = URL("https://www.bing.com/search?q=" + URLEncoder.encode(query, "UTF-8"))
            val conn = endpoint.openConnection() as HttpURLConnection
            conn.requestMethod = "GET"
            conn.connectTimeout = 4000
            conn.readTimeout = 4000
            conn.setRequestProperty("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
            conn.setRequestProperty("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
            conn.setRequestProperty("Accept-Language", "en-US,en;q=0.9")

            if (conn.responseCode == 200) {
                val html = BufferedReader(InputStreamReader(conn.inputStream, "UTF-8")).use { it.readText() }
                parseBingSearchResults(html, maxResults)
            } else {
                emptyList()
            }
        } catch (e: Exception) {
            Log.w(TAG, "[$TAG] Bing web query failed for '$query'", e)
            emptyList()
        }
    }

    fun parseBingSearchResults(html: String, maxResults: Int): List<SearchResult> {
        val results = mutableListOf<SearchResult>()
        val itemRegex = Regex("""<li class="b_algo"[^>]*>(.*?)</li>""", RegexOption.DOT_MATCHES_ALL)
        val h2Regex = Regex("""<h2[^>]*>(.*?)</h2>""", RegexOption.DOT_MATCHES_ALL)
        val linkRegex = Regex("""<a\s+[^>]*href="([^"]+)"[^>]*>(.*?)</a>""", RegexOption.DOT_MATCHES_ALL)
        val captionRegex = Regex("""<div class="b_caption"[^>]*>.*?<p[^>]*>(.*?)</p>""", RegexOption.DOT_MATCHES_ALL)
        val pRegex = Regex("""<p[^>]*>(.*?)</p>""", RegexOption.DOT_MATCHES_ALL)

        val items = itemRegex.findAll(html).toList()
        for (item in items) {
            if (results.size >= maxResults) break
            val itemHtml = item.groupValues[1]

            val h2Match = h2Regex.find(itemHtml) ?: continue
            val linkMatch = linkRegex.find(h2Match.groupValues[1]) ?: continue

            val rawUrl = linkMatch.groupValues[1]
            val rawTitle = linkMatch.groupValues[2]

            val title = cleanHtml(rawTitle)
            val cleanUrl = decodeBingUrl(rawUrl)

            val snipMatch = captionRegex.find(itemHtml) ?: pRegex.find(itemHtml)
            val snippet = if (snipMatch != null) cleanSnippetText(snipMatch.groupValues[1]) else ""

            if (title.isNotBlank() && cleanUrl.isNotBlank() && cleanUrl.startsWith("http")) {
                results.add(SearchResult(title = title, url = cleanUrl, snippet = snippet.ifBlank { title }))
            }
        }
        return results
    }

    fun decodeBingUrl(rawHref: String): String {
        val unescaped = cleanHtml(rawHref)
        val uMatch = Regex("""[?&]u=a1([a-zA-Z0-9_\-]+)""").find(unescaped)
        if (uMatch != null) {
            val b64Candidate = uMatch.groupValues[1]
                .replace('-', '+')
                .replace('_', '/')
            val padded = b64Candidate + "=".repeat((4 - (b64Candidate.length % 4)) % 4)
            try {
                val decodedBytes = java.util.Base64.getDecoder().decode(padded)
                val decodedUrl = String(decodedBytes, Charsets.UTF_8).trim()
                if (decodedUrl.startsWith("http://") || decodedUrl.startsWith("https://")) {
                    return decodedUrl
                }
            } catch (_: Exception) {}
        }
        return cleanUrl(unescaped)
    }

    /**
     * Ranks search candidates by keyword presence, exact phrase matches, and domain quality.
     */
    private fun rankByRelevance(
        results: List<SearchResult>,
        cleanQuery: String,
        maxResults: Int
    ): List<SearchResult> {
        val queryLower = cleanQuery.lowercase()
        // Strip punctuation from query tokens so "SS" matches "S. S." and "S.S."
        val queryTokens = queryLower.replace(Regex("""[^a-z0-9\s]"""), " ")
            .split(Regex("""\s+""")).filter { it.length >= 2 }

        val seenUrls = mutableSetOf<String>()
        val seenTitles = mutableSetOf<String>()
        val scoredList = mutableListOf<Pair<SearchResult, Int>>()

        for (res in results) {
            val normalizedUrl = res.url.trimEnd('/')
            val normTitle = res.title.lowercase().replace(Regex("""[^a-z0-9]"""), "")
            if (normalizedUrl in seenUrls || normTitle in seenTitles) continue

            val titleClean = res.title.lowercase().replace(Regex("""[^a-z0-9\s]"""), " ")
            val snipClean = res.snippet.lowercase().replace(Regex("""[^a-z0-9\s]"""), " ")

            // Base score
            var score = 10

            // Exact phrase match bonus
            if (titleClean.contains(queryLower)) score += 50
            if (snipClean.contains(queryLower)) score += 30

            // Token overlap scoring
            for (token in queryTokens) {
                if (titleClean.contains(token)) score += 15
                if (snipClean.contains(token)) score += 8
            }

            // High-authority encyclopedic / reference platforms get top priority
            val urlLower = res.url.lowercase()
            when {
                urlLower.contains("wikipedia.org") -> score += 35
                urlLower.contains("imdb.com") -> score += 30
                urlLower.contains("linkedin.com") -> score += 20
                urlLower.contains("github.com") -> score += 20
                urlLower.contains("huggingface.co") -> score += 20
                urlLower.contains("gov") || urlLower.contains("edu") -> score += 20
                urlLower.contains("instagram.com") || urlLower.contains("facebook.com") -> score -= 10 // deprioritize social directories below real articles
            }

            seenUrls.add(normalizedUrl)
            seenTitles.add(normTitle)
            scoredList.add(Pair(res, score))
        }

        // Sort descending by relevance score
        scoredList.sortByDescending { it.second }

        val domainCounts = mutableMapOf<String, Int>()
        val diverseList = mutableListOf<SearchResult>()
        for (item in scoredList.map { it.first }) {
            val host = try {
                val hostStr = java.net.URI(item.url).host ?: ""
                hostStr.lowercase().removePrefix("www.")
            } catch (_: Exception) { "" }
            val count = domainCounts.getOrDefault(host, 0)
            if (host.isNotBlank() && count >= 2) continue
            if (host.isNotBlank()) domainCounts[host] = count + 1
            diverseList.add(item)
            if (diverseList.size >= maxResults) break
        }

        if (diverseList.size < maxResults) {
            for (item in scoredList.map { it.first }) {
                if (!diverseList.contains(item)) {
                    diverseList.add(item)
                    if (diverseList.size >= maxResults) break
                }
            }
        }

        return diverseList
    }

    private fun cleanUrl(raw: String): String {
        var url = raw.trim()
        if (url.startsWith("//")) {
            url = "https:$url"
        }
        if (url.contains("uddg=")) {
            val encoded = url.substringAfter("uddg=").substringBefore("&")
            try {
                url = URLDecoder.decode(encoded, "UTF-8")
            } catch (_: Exception) {}
        }
        return url
    }

    private fun cleanSnippetText(raw: String): String {
        var s = cleanHtml(raw)
        s = s.replace(Regex("""\bView (?:the )?profile of [^.]+ on LinkedIn\b""", RegexOption.IGNORE_CASE), "")
        s = s.replace(Regex("""\bSign up to view[^.]*\b""", RegexOption.IGNORE_CASE), "")
        s = s.replace(Regex("""\bJoin to view[^.]*\b""", RegexOption.IGNORE_CASE), "")
        s = s.replace(Regex("""\bSee photos and videos[^.]*\b""", RegexOption.IGNORE_CASE), "")
        s = s.replace(Regex("""\s{2,}"""), " ").trim()
        return s
    }

    private fun cleanHtml(raw: String): String {
        return raw.replace(Regex("<[^>]+>"), "")
            .replace("&#x27;", "'")
            .replace("&#39;", "'")
            .replace("&quot;", "\"")
            .replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&nbsp;", " ")
            .replace("&bull;", "•")
            .replace("&ndash;", "-")
            .replace("&mdash;", "—")
            .replace("&#0183;", "·")
            .replace("&#183;", "·")
            .replace("\uFFFD", " ")
            .trim()
    }
}
