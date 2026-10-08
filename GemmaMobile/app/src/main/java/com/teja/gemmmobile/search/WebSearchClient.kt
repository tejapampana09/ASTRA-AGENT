package com.teja.gemmmobile.search

import androidx.compose.runtime.Immutable
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
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
@Immutable
data class SearchResult(
    val title: String,
    val url: String,
    val snippet: String
)

/**
 * Fast, lightweight on-device web search client using DuckDuckGo Lite.
 * Supports multi-query deep search (like ChatGPT) to fetch rich profiles, projects, and activities.
 * Requires 0 API keys and runs on background IO dispatcher.
 */
open class WebSearchClient {

    fun sanitizeQuery(raw: String): String {
        var query = raw.trim()
        val prefixes = listOf(
            "search the web for ", "search the web ", "search web for ", "search web ",
            "browse the web for ", "please search for ", "please search ", "search for ",
            "search ", "who is ", "who was ", "what is ", "what was ", "tell me about ",
            "look up ", "google for ", "google ", "find "
        )
        for (p in prefixes) {
            if (query.startsWith(p, ignoreCase = true)) {
                val candidate = query.substring(p.length).trim()
                if (candidate.isNotBlank()) {
                    query = candidate
                    break
                }
            }
        }

        // Strip conversational fillers in Telugu and English so the search engine queries the pure subject
        val suffixes = listOf(
            " gurinchi cheppu", " gurinchi", " cheppu", " ante enti", " enti", " telusu",
            " vivarana", " in telugu", " telugu lo", " please", " explain"
        )
        for (s in suffixes) {
            if (query.endsWith(s, ignoreCase = true)) {
                val candidate = query.dropLast(s.length).trim()
                if (candidate.isNotBlank()) {
                    query = candidate
                }
            }
        }

        return query
    }

    private fun generateSubqueries(cleanQuery: String): List<String> {
        val q = cleanQuery.trim()
        if (q.isBlank()) return emptyList()
        val lower = q.lowercase()

        val subqueries = mutableListOf<String>()
        subqueries.add(q)

        // Only add specific platform subqueries if user asked or if looking up a person/entity
        if (lower.contains("linkedin") || lower.contains("profile")) {
            if (!lower.contains("linkedin")) subqueries.add("$q linkedin")
        } else if (lower.startsWith("who is ") || lower.startsWith("tell me about ")) {
            subqueries.add("$q profile")
        }

        if (lower.contains("github") || lower.contains("repo") || lower.contains("code")) {
            if (!lower.contains("github")) subqueries.add("$q github")
        }

        if (lower.contains("latest") || lower.contains("news") || lower.contains("today")) {
            subqueries.add("$q latest news")
        }

        return subqueries.distinct()
    }

    private fun cleanSnippetText(raw: String): String {
        var s = raw
        // Strip follower / connection counters so model doesn't hallucinate conflicting stats
        s = s.replace(Regex("""\b\d+(?:,\d+)?\+?\s+(?:connections?|followers?|following|friends?)\b""", RegexOption.IGNORE_CASE), "")
        s = s.replace(Regex("""\bView (?:the )?profile of [^.]+ on LinkedIn\b""", RegexOption.IGNORE_CASE), "")
        s = s.replace(Regex("""\bSign up to view[^.]*\b""", RegexOption.IGNORE_CASE), "")
        s = s.replace(Regex("""\bJoin to view[^.]*\b""", RegexOption.IGNORE_CASE), "")
        s = s.replace(Regex("""\bSee photos and videos[^.]*\b""", RegexOption.IGNORE_CASE), "")
        s = s.replace(Regex("""\s{2,}"""), " ").trim()
        return s
    }

    open suspend fun search(query: String, maxResults: Int = 10): List<SearchResult> = withContext(Dispatchers.IO) {
        val clean = sanitizeQuery(query)
        if (clean.isBlank()) return@withContext emptyList()

        try {
            Log.d(TAG, "[$TAG] Initiating search for: '$clean'")
            val subqueries = generateSubqueries(clean)
            val (allResults, instantAnswer) = coroutineScope {
                val resultsDeferred = async {
                    subqueries.map { sq ->
                        async { fetchSingleQuery(sq, 6) }
                    }.awaitAll().flatten()
                }
                val instantDeferred = async { fetchInstantAnswer(clean) }
                Pair(resultsDeferred.await(), instantDeferred.await())
            }

            // Deduplicate and filter out low-quality social directory spam and conflicting duplicates
            val seenUrls = mutableSetOf<String>()
            val seenTitles = mutableSetOf<String>()
            val domainCounts = mutableMapOf<String, Int>()
            val filtered = mutableListOf<SearchResult>()

            // If Instant Answer is available, prepend it as high-confidence top summary
            if (instantAnswer != null && instantAnswer.snippet.isNotBlank()) {
                seenUrls.add(instantAnswer.url.trimEnd('/'))
                seenTitles.add(instantAnswer.title.lowercase().replace(Regex("""[^a-z0-9]"""), ""))
                filtered.add(instantAnswer)
            }

            val queryWords = clean.lowercase().split(Regex("""\s+""")).filter { it.length > 2 }

            for (res in allResults) {
                val normalizedUrl = res.url.trimEnd('/')
                val normTitle = res.title.lowercase().replace(Regex("""[^a-z0-9]"""), "")
                if (normalizedUrl in seenUrls || normTitle in seenTitles) continue

                val domain = try {
                    java.net.URI(res.url).host?.removePrefix("www.")?.lowercase() ?: ""
                } catch (_: Exception) { "" }

                // Cap results from any single social domain to avoid mixing up multiple different people
                val isSocialOrProfile = domain.contains("linkedin") || domain.contains("facebook") || domain.contains("instagram")
                val currentDomainCount = domainCounts.getOrDefault(domain, 0)
                if (isSocialOrProfile && currentDomainCount >= 2) {
                    continue
                }

                // Filter out useless social directory boilerplate
                val snipLower = res.snippet.lowercase()
                if (snipLower.contains("11 friends") ||
                    snipLower.contains("facebook gives people the power") ||
                    snipLower.contains("photos and videos from friends on instagram") ||
                    snipLower.contains("see photos and videos") ||
                    res.title.equals("facebook", ignoreCase = true) ||
                    res.title.contains("instagram photos", ignoreCase = true)
                ) {
                    continue
                }

                // If query has specific words, ensure at least some token overlap in title or snippet
                if (queryWords.isNotEmpty()) {
                    val combinedText = "${res.title} ${res.snippet}".lowercase()
                    val hasTokenMatch = queryWords.any { word -> combinedText.contains(word) }
                    if (!hasTokenMatch) continue
                }

                seenUrls.add(normalizedUrl)
                seenTitles.add(normTitle)
                domainCounts[domain] = currentDomainCount + 1

                val cleanedSnippet = cleanSnippetText(res.snippet)
                filtered.add(res.copy(snippet = cleanedSnippet.ifBlank { res.snippet }))
            }

            if (filtered.isNotEmpty()) {
                val finalResults = filtered.take(maxResults)
                Log.d(TAG, "[$TAG] Curated ${finalResults.size} search results")
                return@withContext finalResults
            }

            // Fallback to single query if nothing matched
            fetchSingleQuery(clean, maxResults)
        } catch (t: Throwable) {
            Log.e(TAG, "[$TAG] Search failed, attempting fallback", t)
            fetchHtmlFallback(clean, maxResults)
        }
    }

    private fun fetchInstantAnswer(query: String): SearchResult? {
        return try {
            val endpoint = URL("https://api.duckduckgo.com/?q=" + URLEncoder.encode(query, "UTF-8") + "&format=json&no_html=1&skip_disambig=1")
            val conn = endpoint.openConnection() as HttpURLConnection
            conn.requestMethod = "GET"
            conn.connectTimeout = 3000
            conn.readTimeout = 3000
            conn.setRequestProperty("User-Agent", "Mozilla/5.0 (Linux; Android 14; Mobile)")
            if (conn.responseCode == 200) {
                val json = BufferedReader(InputStreamReader(conn.inputStream, "UTF-8")).use { it.readText() }
                val root = com.google.gson.JsonParser.parseString(json).asJsonObject
                val abstractText = root.get("AbstractText")?.asString?.trim() ?: ""
                val heading = root.get("Heading")?.asString?.trim() ?: ""
                val abstractUrl = root.get("AbstractURL")?.asString?.trim() ?: ""
                val source = root.get("AbstractSource")?.asString?.trim() ?: ""

                if (abstractText.isNotBlank()) {
                    val title = if (heading.isNotBlank()) {
                        if (source.isNotBlank()) "$heading - $source" else heading
                    } else query
                    val url = if (abstractUrl.isNotBlank()) abstractUrl else "https://duckduckgo.com/?q=${URLEncoder.encode(query, "UTF-8")}"
                    SearchResult(
                        title = title,
                        url = url,
                        snippet = abstractText
                    )
                } else null
            } else null
        } catch (_: Exception) {
            null
        }
    }

    private fun fetchSingleQuery(query: String, maxResults: Int): List<SearchResult> {
        // 1. Primary zero-cost engine: Bing Web Search (rich, multi-sentence snippets & current results)
        val bingResults = fetchBingWeb(query, maxResults)
        if (bingResults.isNotEmpty()) {
            return bingResults
        }

        // 2. High-reliability fallback: DuckDuckGo Lite
        return fetchDuckDuckGoLite(query, maxResults)
    }

    fun fetchBingWeb(query: String, maxResults: Int): List<SearchResult> {
        return try {
            val endpoint = URL("https://www.bing.com/search?q=" + URLEncoder.encode(query, "UTF-8"))
            val conn = endpoint.openConnection() as HttpURLConnection
            conn.requestMethod = "GET"
            conn.connectTimeout = 4500
            conn.readTimeout = 4500
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
            Log.w(TAG, "[$TAG] Bing web query failed for '$query', falling back to DDG", e)
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
            val snippet = if (snipMatch != null) cleanHtml(snipMatch.groupValues[1]) else ""

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

    private fun fetchDuckDuckGoLite(query: String, maxResults: Int): List<SearchResult> {
        return try {
            val endpoint = URL("https://lite.duckduckgo.com/lite/")
            val conn = endpoint.openConnection() as HttpURLConnection
            conn.requestMethod = "POST"
            conn.connectTimeout = 4000
            conn.readTimeout = 4000
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
                parseSearchResults(html, maxResults)
            } else {
                fetchHtmlFallback(query, maxResults)
            }
        } catch (e: Exception) {
            Log.w(TAG, "[$TAG] Single query failed for '$query'", e)
            fetchHtmlFallback(query, maxResults)
        }
    }

    private fun fetchHtmlFallback(query: String, maxResults: Int): List<SearchResult> {
        return try {
            val endpoint = URL("https://html.duckduckgo.com/html/?q=" + URLEncoder.encode(query, "UTF-8"))
            val conn = endpoint.openConnection() as HttpURLConnection
            conn.requestMethod = "GET"
            conn.connectTimeout = 5000
            conn.readTimeout = 5000
            conn.setRequestProperty("User-Agent", "Mozilla/5.0 (Linux; Android 14; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36")
            conn.setRequestProperty("Accept", "text/html,application/xhtml+xml")
            if (conn.responseCode == 200) {
                val html = BufferedReader(InputStreamReader(conn.inputStream, "UTF-8")).use { it.readText() }
                parseSearchResults(html, maxResults)
            } else emptyList()
        } catch (e: Exception) {
            Log.w(TAG, "[$TAG] Fallback search also failed", e)
            emptyList()
        }
    }

    private fun parseSearchResults(html: String, maxResults: Int): List<SearchResult> {
        val results = mutableListOf<SearchResult>()

        // 1. Try DuckDuckGo Lite markup (table rows with result-link and result-snippet)
        val liteTagRegex = Regex("""<a\s+([^>]*class=['"][^'"]*result-link[^'"]*['"][^>]*)>(.*?)</a>""", RegexOption.DOT_MATCHES_ALL)
        val liteSnippetRegex = Regex("""<td[^>]*class=['"][^'"]*result-snippet[^'"]*['"][^>]*>(.*?)</td>""", RegexOption.DOT_MATCHES_ALL)
        val hrefRegex = Regex("""href=['"]([^'"]+)['"]""")

        val liteLinks = liteTagRegex.findAll(html).toList()
        val liteSnippets = liteSnippetRegex.findAll(html).toList()

        if (liteLinks.isNotEmpty()) {
            val count = minOf(liteLinks.size, maxResults)
            for (i in 0 until count) {
                val attrs = liteLinks[i].groupValues[1]
                val rawTitle = liteLinks[i].groupValues[2]
                val hrefMatch = hrefRegex.find(attrs)
                val rawUrl = hrefMatch?.groupValues?.get(1)?.let { cleanHtml(it) } ?: ""
                val url = cleanUrl(rawUrl)
                val title = cleanHtml(rawTitle)
                val snippet = if (i < liteSnippets.size) cleanHtml(liteSnippets[i].groupValues[1]) else ""

                if (title.isNotBlank() && url.isNotBlank()) {
                    results.add(SearchResult(title = title, url = url, snippet = snippet.ifBlank { title }))
                }
            }
        }

        // 2. If lite returned empty, try DuckDuckGo HTML markup (result__a and result__snippet)
        if (results.isEmpty()) {
            val htmlTagRegex = Regex("""<a\s+[^>]*class=['"][^'"]*result__a[^'"]*['"][^>]*href=['"]([^'"]+)['"][^>]*>(.*?)</a>""", RegexOption.DOT_MATCHES_ALL)
            val htmlSnippetRegex = Regex("""<a\s+[^>]*class=['"][^'"]*(?:result__snippet|snippet)[^'"]*['"][^>]*>(.*?)</a>""", RegexOption.DOT_MATCHES_ALL)

            val htmlLinks = htmlTagRegex.findAll(html).toList()
            val htmlSnippets = htmlSnippetRegex.findAll(html).toList()

            val count = minOf(htmlLinks.size, maxResults)
            for (i in 0 until count) {
                val rawUrl = htmlLinks[i].groupValues[1]
                val rawTitle = htmlLinks[i].groupValues[2]
                val url = cleanUrl(cleanHtml(rawUrl))
                val title = cleanHtml(rawTitle)
                val snippet = if (i < htmlSnippets.size) cleanHtml(htmlSnippets[i].groupValues[1]) else ""

                if (title.isNotBlank() && url.isNotBlank()) {
                    results.add(SearchResult(title = title, url = url, snippet = snippet.ifBlank { title }))
                }
            }
        }

        return results
    }

    private fun cleanUrl(raw: String): String {
        var url = raw.trim()
        if (url.startsWith("//")) {
            url = "https:$url"
        }
        if (url.contains("uddg=")) {
            val encoded = url.substringAfter("uddg=").substringBefore("&")
            try {
                url = java.net.URLDecoder.decode(encoded, "UTF-8")
            } catch (_: Exception) {}
        }
        return url
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
            .replace("\uFFFD", "·")
            .trim()
    }
}
