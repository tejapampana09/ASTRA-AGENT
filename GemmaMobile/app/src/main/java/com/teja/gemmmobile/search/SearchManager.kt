package com.teja.gemmmobile.search

import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withPermit
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import java.net.HttpURLConnection
import java.net.URI
import java.net.URL
import java.net.URLEncoder
import com.google.gson.JsonParser

private const val TAG = "SearchManager"

/**
 * Enriched search result containing title, source URL, search snippet,
 * and extracted public page content.
 */
data class EnrichedSearchResult(
    val title: String,
    val url: String,
    val snippet: String,
    val pageContent: String = "",
    val fetchSucceeded: Boolean = false,
    val imageUrl: String? = null
) {
    /**
     * Converts to lightweight UI SearchResult for chat cards and profile avatars.
     */
    fun toSearchResult(): SearchResult = SearchResult(
        title = title,
        url = url,
        snippet = snippet
    )
}

/**
 * Central orchestrator for ₹0 on-device web search.
 * Pipeline:
 * User Query -> WebSearchClient (DuckDuckGo Lite / Multi-query)
 *            -> Normalize & Deduplicate
 *            -> Domain Diversity Ranking (Top 5)
 *            -> WebPageFetcher (Bounded concurrency of 3, per-page timeouts)
 *            -> EnrichedSearchResult[]
 */
class SearchManager(
    private val webSearchClient: WebSearchClient = WebSearchClient(),
    private val webPageFetcher: WebPageFetcher = WebPageFetcher()
) {

    companion object {
        const val MAX_CONCURRENT_FETCHES = 3
        const val PER_PAGE_TIMEOUT_MS = 4500L
        const val DEFAULT_MAX_RESULTS = 5
        const val MAX_PAGES_TO_FETCH = 5

        private val TRACKING_PARAMS = setOf(
            "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
            "fbclid", "gclid", "ref", "ved", "usqp", "source", "srsltid"
        )
    }

    /**
     * Normalizes a URL by stripping tracking parameters, fragments, and standardizing host case.
     */
    fun normalizeUrl(rawUrl: String): String {
        return try {
            val uri = URI(rawUrl.trim())
            val scheme = (uri.scheme ?: "https").lowercase()
            val host = (uri.host ?: "").lowercase()
            val rawPath = uri.path ?: ""
            val cleanPath = if (rawPath.length > 1 && rawPath.endsWith("/")) rawPath.removeSuffix("/") else rawPath

            // Strip tracking query parameters
            val cleanQuery = uri.query?.split("&")
                ?.filter { param ->
                    val key = param.substringBefore("=").lowercase()
                    key !in TRACKING_PARAMS
                }
                ?.joinToString("&")
                ?.ifBlank { null }

            val portPart = if (uri.port != -1 && uri.port != 80 && uri.port != 443) ":${uri.port}" else ""
            val queryPart = if (!cleanQuery.isNullOrBlank()) "?$cleanQuery" else ""

            "$scheme://$host$portPart$cleanPath$queryPart"
        } catch (_: Exception) {
            rawUrl.trim().removeSuffix("/")
        }
    }

    /**
     * Extracts normalized domain host from a URL string for domain diversity checking.
     */
    fun extractDomain(url: String): String {
        return try {
            URI(url).host?.lowercase()?.removePrefix("www.") ?: ""
        } catch (_: Exception) {
            ""
        }
    }

    /**
     * Deduplicates and balances search results to maximize domain diversity.
     */
    fun deduplicateAndRank(results: List<SearchResult>, maxResults: Int): List<SearchResult> {
        val seenUrls = mutableSetOf<String>()
        val seenTitles = mutableSetOf<String>()
        val domainCounts = mutableMapOf<String, Int>()

        val primaryCandidates = mutableListOf<SearchResult>()
        val overflowCandidates = mutableListOf<SearchResult>()

        for (res in results) {
            val normUrl = normalizeUrl(res.url)
            val normTitle = res.title.trim().lowercase()

            if (normUrl.isBlank() || !webPageFetcher.isSafeUrl(normUrl)) continue
            if (normTitle.isBlank()) continue

            // Deduplicate by URL and exact title
            if (!seenUrls.add(normUrl)) continue
            if (!seenTitles.add(normTitle)) continue

            val domain = extractDomain(normUrl)
            val count = domainCounts.getOrDefault(domain, 0)

            // Favor domain diversity: allow max 2 results from the same domain in primary selection
            if (domain.isBlank() || count < 2) {
                domainCounts[domain] = count + 1
                primaryCandidates.add(res.copy(url = normUrl))
            } else {
                overflowCandidates.add(res.copy(url = normUrl))
            }

            if (primaryCandidates.size >= maxResults) break
        }

        val finalSelection = (primaryCandidates + overflowCandidates).take(maxResults)
        return finalSelection
    }

    /**
     * Orchestrates DuckDuckGo search + concurrent webpage content extraction.
     */
    suspend fun searchAndRead(
        query: String,
        maxResults: Int = DEFAULT_MAX_RESULTS
    ): List<EnrichedSearchResult> = withContext(Dispatchers.IO) {
        val cleanQuery = webSearchClient.sanitizeQuery(query)
        if (cleanQuery.isBlank()) return@withContext emptyList()

        Log.d(TAG, "[$TAG] Executing searchAndRead for query: \"$cleanQuery\"")

        // 1. Fetch raw search results from DuckDuckGo
        val rawResults = try {
            webSearchClient.search(cleanQuery, maxResults = 12)
        } catch (t: Throwable) {
            Log.w(TAG, "[$TAG] DuckDuckGo search failed: ${t.localizedMessage}")
            emptyList()
        }

        if (rawResults.isEmpty()) {
            return@withContext emptyList()
        }

        // 2. Deduplicate, filter junk/unsafe targets, and ensure domain diversity
        val rankedResults = deduplicateAndRank(rawResults, maxResults)
        Log.d(TAG, "[$TAG] Filtered to ${rankedResults.size} diverse candidate URLs")

        // 3. Concurrently fetch top public pages with bounded semaphore concurrency
        val semaphore = Semaphore(MAX_CONCURRENT_FETCHES)

        coroutineScope {
            val deferredEnriched = rankedResults.take(MAX_PAGES_TO_FETCH).map { res ->
                async {
                    var fetchedContent = ""
                    var fetchSuccess = false
                    var fetchedImage: String? = null

                    try {
                        semaphore.withPermit {
                            // Enforce per-page timeout
                            val fetched = withTimeoutOrNull(PER_PAGE_TIMEOUT_MS) {
                                webPageFetcher.fetchPage(res.url)
                            }

                            if (fetched != null && fetched.success && fetched.content.isNotBlank()) {
                                fetchedContent = fetched.content
                                fetchSuccess = true
                                fetchedImage = fetched.imageUrl
                                Log.d(TAG, "[$TAG] Successfully fetched ${fetchedContent.length} chars from ${res.url}")
                            } else {
                                Log.d(TAG, "[$TAG] Page fetch skipped/failed for ${res.url}; falling back to snippet")
                            }
                        }
                    } catch (t: Throwable) {
                        Log.w(TAG, "[$TAG] Error fetching ${res.url}: ${t.localizedMessage}")
                    }

                    EnrichedSearchResult(
                        title = res.title,
                        url = res.url,
                        snippet = res.snippet,
                        pageContent = fetchedContent,
                        fetchSucceeded = fetchSuccess,
                        imageUrl = fetchedImage
                    )
                }
            }

            deferredEnriched.awaitAll()
        }
    }

    /**
     * Extracts and retrieves high-signal search images for inline chat display (ChatGPT style).
     * Collects OpenGraph images from verified fetched pages and queries DuckDuckGo image search.
     */
    suspend fun searchImages(
        query: String,
        enrichedPages: List<EnrichedSearchResult> = emptyList(),
        maxImages: Int = 8
    ): List<SearchImage> = withContext(Dispatchers.IO) {
        val images = mutableListOf<SearchImage>()
        val seenUrls = mutableSetOf<String>()

        // 1. Gather high-fidelity OpenGraph images from verified public webpages
        for (page in enrichedPages) {
            val img = page.imageUrl
            if (!img.isNullOrBlank() && seenUrls.add(img)) {
                images.add(
                    SearchImage(
                        title = page.title,
                        imageUrl = img,
                        sourceUrl = page.url,
                        sourceDomain = extractDomain(page.url)
                    )
                )
            }
        }

        // 2. Fetch additional high-res images directly from DuckDuckGo Image Search
        if (images.size < maxImages) {
            val ddgImages = fetchDuckDuckGoImages(query, maxImages - images.size)
            for (ddgImg in ddgImages) {
                if (seenUrls.add(ddgImg.imageUrl)) {
                    images.add(ddgImg)
                }
            }
        }

        images.take(maxImages)
    }

    private fun fetchDuckDuckGoImages(query: String, limit: Int): List<SearchImage> {
        if (query.isBlank() || limit <= 0) return emptyList()
        try {
            val encodedQuery = URLEncoder.encode(query, "UTF-8")
            // Step 1: obtain vqd token
            val tokenUrl = "https://duckduckgo.com/?q=$encodedQuery"
            val conn = (URL(tokenUrl).openConnection() as HttpURLConnection).apply {
                connectTimeout = 3000
                readTimeout = 3000
                requestMethod = "GET"
                setRequestProperty("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            }
            val html = conn.inputStream.bufferedReader().use { it.readText() }
            conn.disconnect()

            val vqdMatch = Regex("""vqd=["']?([0-9-]+)["']?""").find(html)
                ?: Regex("""vqd=([0-9-]+)""").find(html)
            val vqd = vqdMatch?.groupValues?.get(1) ?: return emptyList()

            // Step 2: Query image API endpoint
            val imgApiUrl = "https://duckduckgo.com/i.js?l=us-en&o=json&q=$encodedQuery&vqd=$vqd&f=,,,"
            val apiConn = (URL(imgApiUrl).openConnection() as HttpURLConnection).apply {
                connectTimeout = 3500
                readTimeout = 3500
                requestMethod = "GET"
                setRequestProperty("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
                setRequestProperty("Accept", "application/json")
            }
            if (apiConn.responseCode != 200) {
                apiConn.disconnect()
                return emptyList()
            }
            val jsonText = apiConn.inputStream.bufferedReader().use { it.readText() }
            apiConn.disconnect()

            val jsonObject = JsonParser.parseString(jsonText).asJsonObject
            val resultsArray = jsonObject.getAsJsonArray("results") ?: return emptyList()

            val ddgList = mutableListOf<SearchImage>()
            for (elem in resultsArray) {
                if (ddgList.size >= limit) break
                val obj = elem.asJsonObject
                val imgUrl = obj.get("image")?.asString ?: continue
                val title = obj.get("title")?.asString ?: query
                val srcUrl = obj.get("url")?.asString ?: imgUrl
                if (webPageFetcher.isSafeUrl(imgUrl)) {
                    ddgList.add(
                        SearchImage(
                            title = title,
                            imageUrl = imgUrl,
                            sourceUrl = srcUrl,
                            sourceDomain = extractDomain(srcUrl)
                        )
                    )
                }
            }
            return ddgList
        } catch (_: Exception) {
            return emptyList()
        }
    }

    /**
     * Formats enriched search results into a clean, verified context block for Gemma's prompt.
     * Tells the model to ground answers on the extracted webpage content and cite source URLs.
     */
    fun formatGemmaWebContext(
        results: List<EnrichedSearchResult>,
        maxTotalChars: Int = 6500
    ): String {
        if (results.isEmpty()) return ""

        val sb = StringBuilder()
        sb.appendLine("## REAL-TIME WEB SEARCH EVIDENCE")
        sb.appendLine("The following sources were retrieved and verified live from the public web:")
        sb.appendLine()

        var currentChars = sb.length

        for ((idx, res) in results.withIndex()) {
            val itemSb = StringBuilder()
            itemSb.appendLine("[${idx + 1}] Title: ${res.title}")
            itemSb.appendLine("URL: ${res.url}")
            itemSb.appendLine("Search Snippet: ${res.snippet}")

            if (res.fetchSucceeded && res.pageContent.isNotBlank()) {
                // Take up to 1,800 chars of page content per source to balance multi-source evidence
                val boundedPageContent = res.pageContent.take(1800).trim()
                itemSb.appendLine("Extracted Webpage Content:")
                itemSb.appendLine(boundedPageContent)
            } else {
                itemSb.appendLine("Page content: Unavailable (rely on verified search snippet above)")
            }
            itemSb.appendLine()

            if (currentChars + itemSb.length > maxTotalChars && idx > 0) {
                break
            }

            sb.append(itemSb)
            currentChars += itemSb.length
        }

        return sb.toString().trim()
    }
}
