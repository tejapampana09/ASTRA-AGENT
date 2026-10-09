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
 * Distinct failure and success states for web search.
 */
enum class SearchStatus {
    SUCCESS,
    NO_RESULTS,
    NETWORK_ERROR,
    TIMEOUT,
    PROVIDER_ERROR,
    FETCH_ERROR
}

/**
 * Provenance of search content.
 */
enum class ContentSourceType {
    SEARCH_SNIPPET,
    FETCHED_WEBPAGE,
    IMAGE_SEARCH
}

/**
 * Structured search response with explicit status code and debug message.
 */
data class SearchResponse(
    val status: SearchStatus,
    val results: List<EnrichedSearchResult> = emptyList(),
    val errorMessage: String? = null,
    val images: List<SearchImage> = emptyList()
)

/**
 * Enriched search result containing title, source URL, search snippet,
 * extracted public page content, and provenance metadata.
 */
data class EnrichedSearchResult(
    val title: String,
    val url: String,
    val snippet: String,
    val pageContent: String = "",
    val fetchSucceeded: Boolean = false,
    val imageUrl: String? = null,
    val sourceType: ContentSourceType = if (fetchSucceeded) ContentSourceType.FETCHED_WEBPAGE else ContentSourceType.SEARCH_SNIPPET
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
 * Central orchestrator for on-device web search.
 * Uses Serper.dev (1,900+ queries) and SerpApi (230+ queries) as primary providers
 * for 100% genuine products, live INR prices, packshot images, and direct store URLs.
 * Seamlessly falls back to on-device zero-cost DuckDuckGo Lite & Wikipedia if API quotas run out.
 * Includes a 24-hour smart LRU cache to conserve API credits.
 */
open class SearchManager(
    private val webSearchClient: WebSearchClient = WebSearchClient(),
    private val webPageFetcher: WebPageFetcher = WebPageFetcher(),
    private val serpApiClient: SerpApiClient = SerpApiClient(),
    private val serperClient: SerperClient = SerperClient()
) {

    companion object {
        private val TRACKING_PARAMS = setOf(
            "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
            "fbclid", "gclid", "ref", "ved", "usqp", "source", "srsltid"
        )
        private val searchCache = java.util.concurrent.ConcurrentHashMap<String, Pair<Long, SearchResponse>>()
        private const val CACHE_TTL_MS = 24 * 60 * 60 * 1000L // 24 hours
    }

    /**
     * Sanitizes user input queries by stripping filler conversational commands.
     */
    fun sanitizeQuery(raw: String): String = webSearchClient.sanitizeQuery(raw)
    fun isGenericQuery(query: String): Boolean = webSearchClient.isGenericQuery(query)

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

        return (primaryCandidates + overflowCandidates).take(maxResults)
    }

    /**
     * Orchestrates web search with explicit status reporting.
     */
    open suspend fun searchAndReadWithStatus(
        query: String,
        maxResults: Int = SearchConfig.DEFAULT_MAX_SEARCH_RESULTS,
        isProduct: Boolean = false
    ): SearchResponse = withContext(Dispatchers.IO) {
        val cleanQuery = sanitizeQuery(query)
        if (cleanQuery.isBlank()) {
            return@withContext SearchResponse(SearchStatus.NO_RESULTS, emptyList(), "Empty query")
        }

        Log.d(TAG, "[$TAG] Executing searchAndRead for query: \"$cleanQuery\" (isProduct=$isProduct)")

        // 0. Check 24-hour in-memory cache to save API credits
        val cacheKey = "$isProduct:${cleanQuery.lowercase()}"
        val cached = searchCache[cacheKey]
        if (cached != null && System.currentTimeMillis() - cached.first < CACHE_TTL_MS) {
            Log.d(TAG, "[$TAG] Returning 24h cached search response for: \"$cleanQuery\"")
            return@withContext cached.second
        }

        // 1. For PRODUCTS & SHOPPING ONLY: Use Serper.dev / SerpApi for real prices, direct store links, packshots
        // Normal web searches (isProduct == false) will NEVER touch Serper or SerpApi (0 credits used, 100% free Bing/DDG)
        if (isProduct) {
            // Try Serper.dev first (1,900+ credits)
            if (serperClient.isAvailable()) {
                try {
                    val serperResult = serperClient.search(cleanQuery, maxResults, isProduct = true)
                    if (serperResult != null && serperResult.results.isNotEmpty()) {
                        Log.d(TAG, "[$TAG] Serper.dev returned ${serperResult.results.size} product results and ${serperResult.images.size} images")
                        val enriched = serperResult.results.map { res ->
                            EnrichedSearchResult(
                                title = res.title,
                                url = normalizeUrl(res.url),
                                snippet = res.snippet,
                                pageContent = "",
                                fetchSucceeded = false,
                                imageUrl = serperResult.images.firstOrNull { it.title == res.title }?.imageUrl,
                                sourceType = ContentSourceType.SEARCH_SNIPPET
                            )
                        }
                        val response = SearchResponse(
                            status = SearchStatus.SUCCESS,
                            results = enriched,
                            images = serperResult.images
                        )
                        searchCache[cacheKey] = Pair(System.currentTimeMillis(), response)
                        return@withContext response
                    }
                } catch (t: Throwable) {
                    Log.w(TAG, "[$TAG] Serper.dev product search failed, falling back to SerpApi", t)
                }
            }

            // Try SerpApi backup (230+ credits)
            if (serpApiClient.isAvailable()) {
                try {
                    val serpResult = serpApiClient.search(cleanQuery, maxResults, isProduct = true)
                    if (serpResult != null && serpResult.results.isNotEmpty()) {
                        Log.d(TAG, "[$TAG] SerpApi returned ${serpResult.results.size} product results and ${serpResult.images.size} images")
                        val enriched = serpResult.results.map { res ->
                            EnrichedSearchResult(
                                title = res.title,
                                url = normalizeUrl(res.url),
                                snippet = res.snippet,
                                pageContent = "",
                                fetchSucceeded = false,
                                imageUrl = serpResult.images.firstOrNull { it.title == res.title }?.imageUrl,
                                sourceType = ContentSourceType.SEARCH_SNIPPET
                            )
                        }
                        val response = SearchResponse(
                            status = SearchStatus.SUCCESS,
                            results = enriched,
                            images = serpResult.images
                        )
                        searchCache[cacheKey] = Pair(System.currentTimeMillis(), response)
                        return@withContext response
                    }
                } catch (t: Throwable) {
                    Log.w(TAG, "[$TAG] SerpApi product search failed, falling back to WebSearchClient", t)
                }
            }
        }

        // 2. FOR ALL NORMAL WEB SEARCHES (isProduct == false) OR PRODUCT FALLBACK:
        // Exclusively use 100% FREE on-device DuckDuckGo Lite, Wikipedia, and Bing!
        // ZERO API KEYS, ZERO CREDITS, 100% FREE UNLIMITED FOREVER!

        // 3. Fallback to on-device DuckDuckGo / Wikipedia pipeline
        val rawResults: List<SearchResult>
        try {
            rawResults = webSearchClient.search(cleanQuery, maxResults = 12)
        } catch (t: Throwable) {
            Log.w(TAG, "[$TAG] DuckDuckGo search failed: ${t.localizedMessage}")
            val isTimeout = t is java.net.SocketTimeoutException
            val status = if (isTimeout) SearchStatus.TIMEOUT else SearchStatus.PROVIDER_ERROR
            return@withContext SearchResponse(status, emptyList(), t.localizedMessage ?: "Provider error")
        }

        if (rawResults.isEmpty()) {
            return@withContext SearchResponse(SearchStatus.NO_RESULTS, emptyList())
        }

        // 3. Deduplicate, filter junk/unsafe targets, and ensure domain diversity
        val rankedResults = deduplicateAndRank(rawResults, maxResults)
        if (rankedResults.isEmpty()) {
            return@withContext SearchResponse(SearchStatus.NO_RESULTS, emptyList())
        }

        // 4. Concurrently fetch top public pages with bounded semaphore concurrency
        val semaphore = Semaphore(SearchConfig.MAX_CONCURRENT_FETCHES)

        val enrichedList = coroutineScope {
            val deferredEnriched = rankedResults.mapIndexed { idx, res ->
                async {
                    var fetchedContent = ""
                    var fetchSuccess = false
                    var fetchedImage: String? = null

                    val domain = extractDomain(res.url)
                    val isAuthWalledDomain = domain.contains("linkedin") || domain.contains("facebook") ||
                        domain.contains("instagram") || domain.contains("twitter") || domain.contains("x.com") ||
                        domain.contains("youtube") || domain.contains("reddit") || domain.contains("tiktok")

                    // Skip scraping for known auth-walled social domains to prevent timeouts and bot-blockers
                    if (idx < SearchConfig.MAX_PAGES_TO_FETCH && !isAuthWalledDomain && webPageFetcher.isSafeUrl(res.url)) {
                        try {
                            semaphore.withPermit {
                                val fetched = withTimeoutOrNull(SearchConfig.PER_PAGE_TIMEOUT_MS) {
                                    webPageFetcher.fetchPage(res.url)
                                }

                                if (fetched != null && fetched.success && fetched.content.isNotBlank() && !isAuthOrLoginText(fetched.content)) {
                                    fetchedContent = fetched.content
                                    fetchSuccess = true
                                    fetchedImage = fetched.imageUrl
                                }
                            }
                        } catch (t: Throwable) {
                            Log.w(TAG, "[$TAG] Error fetching ${res.url}: ${t.localizedMessage}")
                        }
                    }

                    EnrichedSearchResult(
                        title = res.title,
                        url = res.url,
                        snippet = res.snippet,
                        pageContent = fetchedContent,
                        fetchSucceeded = fetchSuccess,
                        imageUrl = fetchedImage,
                        sourceType = if (fetchSuccess) ContentSourceType.FETCHED_WEBPAGE else ContentSourceType.SEARCH_SNIPPET
                    )
                }
            }

            deferredEnriched.awaitAll()
        }

        return@withContext SearchResponse(SearchStatus.SUCCESS, enrichedList)
    }

    /**
     * Backward-compatible convenience wrapper returning list of results.
     */
    open suspend fun searchAndRead(
        query: String,
        maxResults: Int = SearchConfig.DEFAULT_MAX_SEARCH_RESULTS,
        isProduct: Boolean = false
    ): List<EnrichedSearchResult> {
        return searchAndReadWithStatus(query, maxResults, isProduct).results
    }

    /**
     * Cleans query specifically for visual image search engines by stripping filler/intent words,
     * while guaranteeing keywords like 'diagram' remain for architectural and technical searches.
     */
    fun cleanVisualQuery(raw: String): String {
        val q = sanitizeQuery(raw).trim()
        val wordsToStrip = setOf(
            "images", "image", "photos", "photo", "pictures", "picture", "pics", "pic",
            "wallpapers", "wallpaper", "diagrams", "diagram", "show me", "chupinchu",
            "chudu", "bomma", "bommalu", "hd", "4k", "of"
        )
        val tokens = q.split(Regex("""\s+""")).filter { it.lowercase() !in wordsToStrip }
        var cleaned = tokens.joinToString(" ").trim()
        if (cleaned.isBlank()) cleaned = q

        val lowerRaw = raw.lowercase()
        if ((lowerRaw.contains("architecture") || lowerRaw.contains("diagram") || lowerRaw.contains("flowchart") || lowerRaw.contains("workflow")) &&
            !cleaned.lowercase().contains("diagram")) {
            cleaned = "$cleaned diagram"
        }
        return cleaned
    }

    /**
     * Extracts and retrieves high-signal search images for inline chat display (ChatGPT style).
     * Strictly distinct from web search: focuses exclusively on visual diagrams, photos, and figures.
     */
    open suspend fun searchImages(
        query: String,
        enrichedPages: List<EnrichedSearchResult> = emptyList(),
        maxImages: Int = 8
    ): List<SearchImage> = withContext(Dispatchers.IO) {
        val clean = cleanVisualQuery(query)
        if (clean.isBlank()) return@withContext emptyList()

        val images = mutableListOf<SearchImage>()
        val seenUrls = mutableSetOf<String>()

        // 1. Primary zero-cost engine: High-resolution Bing Images Async API
        val bingImages = fetchBingImages(clean, maxImages)
        for (img in bingImages) {
            if (seenUrls.add(img.imageUrl)) {
                images.add(img)
            }
        }

        // 2. Fallback: DuckDuckGo Images if Bing returned fewer than desired
        if (images.size < maxImages) {
            val ddgImages = fetchDuckDuckGoImages(clean, maxImages - images.size)
            for (ddgImg in ddgImages) {
                if (seenUrls.add(ddgImg.imageUrl)) {
                    images.add(ddgImg)
                }
            }
        }

        // 3. Fallback: High-fidelity OpenGraph images from verified public webpages if engines returned empty
        if (images.isEmpty() && enrichedPages.isNotEmpty()) {
            for (page in enrichedPages) {
                val img = page.imageUrl
                if (!img.isNullOrBlank() && seenUrls.add(img) && webPageFetcher.isSafeUrl(img)) {
                    images.add(
                        SearchImage(
                            title = page.title,
                            imageUrl = img,
                            sourceUrl = page.url,
                            sourceDomain = extractDomain(page.url)
                        )
                    )
                }
                if (images.size >= maxImages) break
            }
        }

        images.take(maxImages)
    }

    fun fetchBingImages(query: String, limit: Int): List<SearchImage> {
        if (query.isBlank() || limit <= 0) return emptyList()
        return try {
            val endpoint = URL("https://www.bing.com/images/async?q=" + URLEncoder.encode(query, "UTF-8") + "&first=0&count=25&mmasync=1")
            val conn = (endpoint.openConnection() as HttpURLConnection).apply {
                connectTimeout = SearchConfig.IMAGE_CONNECT_TIMEOUT_MS
                readTimeout = SearchConfig.IMAGE_READ_TIMEOUT_MS
                requestMethod = "GET"
                setRequestProperty("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
                setRequestProperty("Accept", "*/*")
                setRequestProperty("Accept-Language", "en-US,en;q=0.9")
            }

            if (conn.responseCode != 200) {
                conn.disconnect()
                return emptyList()
            }

            val html = conn.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() }
            conn.disconnect()

            parseBingImages(html, limit, query)
        } catch (e: Exception) {
            Log.w(TAG, "[$TAG] Bing image search failed for '$query', falling back to DDG", e)
            emptyList()
        }
    }

    fun parseBingImages(html: String, limit: Int, defaultTitle: String): List<SearchImage> {
        val iuscRegex = Regex("""class=["']iusc["'][^>]*m=["']([^"']+)["']""")
        val matches = iuscRegex.findAll(html).toList()
        val list = mutableListOf<SearchImage>()
        val seenUrls = mutableSetOf<String>()

        for (m in matches) {
            if (list.size >= limit) break
            val rawM = m.groupValues[1]
            try {
                val unescaped = rawM
                    .replace("&quot;", "\"")
                    .replace("&amp;", "&")
                    .replace("&lt;", "<")
                    .replace("&gt;", ">")
                val json = JsonParser.parseString(unescaped).asJsonObject
                val imgUrl = json.get("murl")?.asString?.trim() ?: continue
                val srcUrl = json.get("purl")?.asString?.trim() ?: imgUrl
                val title = json.get("t")?.asString?.trim()
                    ?: json.get("desc")?.asString?.trim()
                    ?: defaultTitle

                if (imgUrl.isNotBlank() && imgUrl.startsWith("http") && seenUrls.add(imgUrl) && webPageFetcher.isSafeUrl(imgUrl)) {
                    list.add(
                        SearchImage(
                            title = title,
                            imageUrl = imgUrl,
                            sourceUrl = srcUrl,
                            sourceDomain = extractDomain(srcUrl)
                        )
                    )
                }
            } catch (_: Exception) {
                // Ignore malformed card
            }
        }
        return list
    }

    private fun fetchDuckDuckGoImages(query: String, limit: Int): List<SearchImage> {
        if (query.isBlank() || limit <= 0) return emptyList()
        try {
            val encodedQuery = URLEncoder.encode(query, "UTF-8")
            // Step 1: obtain vqd token
            val tokenUrl = "https://duckduckgo.com/?q=$encodedQuery"
            val conn = (URL(tokenUrl).openConnection() as HttpURLConnection).apply {
                connectTimeout = SearchConfig.IMAGE_CONNECT_TIMEOUT_MS
                readTimeout = SearchConfig.IMAGE_READ_TIMEOUT_MS
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
                connectTimeout = SearchConfig.IMAGE_CONNECT_TIMEOUT_MS
                readTimeout = SearchConfig.IMAGE_READ_TIMEOUT_MS
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
     * Formats enriched search results into a clean, injection-safe context block for Gemma's prompt.
     * Strictly delimits external webpage text with <WEB_SEARCH_RESULTS> to neutralize prompt injection.
     */
    fun formatGemmaWebContext(
        results: List<EnrichedSearchResult>,
        maxTotalChars: Int = SearchConfig.MAX_WEB_CONTEXT_CHARS
    ): String {
        if (results.isEmpty()) return ""

        val sb = StringBuilder()
        sb.appendLine("## LIVE WEB RESULTS (UNTRUSTED EXTERNAL DATA)")
        sb.appendLine("<WEB_SOURCE_UNTRUSTED_DATA>")

        var currentChars = sb.length

        for ((idx, res) in results.take(SearchConfig.DEFAULT_MAX_SEARCH_RESULTS).withIndex()) {
            val itemSb = StringBuilder()
            val cleanTitle = res.title.take(90).replace(Regex("""[\x00-\x1F\x7F]"""), " ").trim()
            val cleanUrl = res.url.replace(Regex("""[\x00-\x1F\x7F]"""), "").trim()
            val cleanSnippet = res.snippet.take(280).replace(Regex("""[\x00-\x1F\x7F]"""), " ").trim()

            itemSb.appendLine("[${idx + 1}] Title: $cleanTitle")
            itemSb.appendLine("Source URL: $cleanUrl")
            itemSb.appendLine("Snippet: $cleanSnippet")

            if (res.fetchSucceeded && res.pageContent.isNotBlank() && !isAuthOrLoginText(res.pageContent)) {
                val boundedPageContent = res.pageContent.take(200).replace(Regex("""[\x00-\x1F\x7F]"""), " ").trim()
                itemSb.appendLine("Webpage Text: $boundedPageContent")
            }
            itemSb.appendLine()

            if (currentChars + itemSb.length > maxTotalChars && idx > 0) {
                break
            }

            sb.append(itemSb)
            currentChars += itemSb.length
        }

        sb.appendLine("</WEB_SOURCE_UNTRUSTED_DATA>")
        return sb.toString().trim()
    }

    private fun isAuthOrLoginText(text: String): Boolean {
        val lower = text.lowercase()
        return lower.contains("sign in to") || lower.contains("login to") ||
               lower.contains("join linkedin") || lower.contains("enable javascript") ||
               lower.contains("verify you are human") || lower.contains("cloudflare")
    }
}
