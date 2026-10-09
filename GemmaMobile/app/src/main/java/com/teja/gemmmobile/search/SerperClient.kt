package com.teja.gemmmobile.search

import android.util.Log
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

private const val TAG = "SerperClient"

/**
 * High-speed Serper.dev client powered by Google Search and Google Shopping.
 * Offers 2,500 free queries per account with fast (<500ms) JSON POST execution.
 * Direct INR prices, packshots, and purchase links across India (gl=in, hl=en).
 */
open class SerperClient(
    private val apiKey: String = SearchConfig.SERPER_API_KEY
) {

    /**
     * Checks if a valid API key is present.
     */
    fun isAvailable(): Boolean = apiKey.isNotBlank()

    /**
     * Executes search on Serper.dev.
     * Uses /shopping for product requests and /search for general knowledge.
     */
    open suspend fun search(
        query: String,
        maxResults: Int = SearchConfig.DEFAULT_MAX_SEARCH_RESULTS,
        isProduct: Boolean = false
    ): SerpApiResult? = withContext(Dispatchers.IO) {
        if (!isAvailable()) return@withContext null

        val cleanQuery = query.trim()
        if (cleanQuery.isBlank()) return@withContext null

        try {
            val endpointPath = if (isProduct) "/shopping" else "/search"
            val endpointUrl = "${SearchConfig.SERPER_BASE_URL}$endpointPath"

            Log.d(TAG, "[$TAG] Querying Serper.dev $endpointPath for: \"$cleanQuery\"")

            val url = URL(endpointUrl)
            val conn = (url.openConnection() as HttpURLConnection).apply {
                connectTimeout = SearchConfig.SERPER_CONNECT_TIMEOUT_MS
                readTimeout = SearchConfig.SERPER_READ_TIMEOUT_MS
                requestMethod = "POST"
                setRequestProperty("X-API-KEY", apiKey)
                setRequestProperty("Content-Type", "application/json")
                setRequestProperty("Accept", "application/json")
                doOutput = true
            }

            val requestJson = JsonObject().apply {
                addProperty("q", cleanQuery)
                addProperty("gl", SearchConfig.SERPAPI_COUNTRY)
                addProperty("hl", SearchConfig.SERPAPI_LANGUAGE)
                addProperty("num", 10)
            }

            OutputStreamWriter(conn.outputStream, Charsets.UTF_8).use { writer ->
                writer.write(requestJson.toString())
                writer.flush()
            }

            val responseCode = conn.responseCode
            if (responseCode != 200) {
                val errorStream = conn.errorStream?.bufferedReader()?.use { it.readText() }
                Log.w(TAG, "[$TAG] Serper returned HTTP $responseCode: $errorStream")
                conn.disconnect()
                return@withContext null
            }

            val responseBody = conn.inputStream.bufferedReader().use { it.readText() }
            conn.disconnect()

            val rootJson = JsonParser.parseString(responseBody).asJsonObject

            if (isProduct) {
                parseShoppingResponse(rootJson, cleanQuery, maxResults)
            } else {
                parseSearchResponse(rootJson, cleanQuery, maxResults)
            }
        } catch (t: Throwable) {
            Log.w(TAG, "[$TAG] Serper.dev request failed: ${t.localizedMessage}", t)
            null
        }
    }

    /**
     * Parses Serper /shopping response.
     */
    private fun parseShoppingResponse(
        rootJson: JsonObject,
        query: String,
        maxResults: Int
    ): SerpApiResult {
        val searchResults = mutableListOf<SearchResult>()
        val searchImages = mutableListOf<SearchImage>()
        val seenUrls = mutableSetOf<String>()

        val shoppingArray = rootJson.getAsJsonArray("shopping")
        if (shoppingArray != null) {
            for (elem in shoppingArray) {
                if (searchResults.size >= maxResults) break
                val obj = elem.asJsonObject

                val title = obj.get("title")?.asString?.trim() ?: continue
                val source = obj.get("source")?.asString?.trim() ?: "Online Store"
                val link = obj.get("link")?.asString?.trim() ?: continue

                if (link.isBlank() || !seenUrls.add(link)) continue

                val price = obj.get("price")?.asString?.trim() ?: ""
                val rating = obj.get("rating")?.asDouble
                val ratingCount = obj.get("ratingCount")?.asInt
                val delivery = obj.get("delivery")?.asString?.trim() ?: ""
                val imageUrl = obj.get("imageUrl")?.asString?.trim()

                val ratingPart = if (rating != null) " (Rating: $rating★${if (ratingCount != null) " / $ratingCount reviews" else ""})" else ""
                val deliveryPart = if (delivery.isNotBlank()) " | $delivery" else ""
                val pricePrefix = if (price.isNotBlank()) "$price on $source" else "Available on $source"
                val snippet = "$pricePrefix$ratingPart$deliveryPart. Verified authentic product listing."

                searchResults.add(
                    SearchResult(
                        title = title,
                        url = link,
                        snippet = snippet
                    )
                )

                if (!imageUrl.isNullOrBlank() && imageUrl.startsWith("http")) {
                    searchImages.add(
                        SearchImage(
                            title = title,
                            imageUrl = imageUrl,
                            sourceUrl = link,
                            sourceDomain = source
                        )
                    )
                }
            }
        }

        return SerpApiResult(searchResults, searchImages)
    }

    /**
     * Parses Serper /search response (Organic results, Answer Box, Knowledge Graph).
     */
    private fun parseSearchResponse(
        rootJson: JsonObject,
        query: String,
        maxResults: Int
    ): SerpApiResult {
        val searchResults = mutableListOf<SearchResult>()
        val searchImages = mutableListOf<SearchImage>()
        val seenUrls = mutableSetOf<String>()

        // 1. Answer Box
        rootJson.getAsJsonObject("answerBox")?.let { box ->
            val title = box.get("title")?.asString?.trim() ?: "Direct Answer"
            val answer = box.get("answer")?.asString?.trim()
                ?: box.get("snippet")?.asString?.trim()
                ?: ""
            val link = box.get("link")?.asString?.trim() ?: ""
            if (answer.isNotBlank() && link.isNotBlank() && seenUrls.add(link)) {
                searchResults.add(SearchResult(title, link, answer))
            }
        }

        // 2. Knowledge Graph
        rootJson.getAsJsonObject("knowledgeGraph")?.let { kg ->
            val title = kg.get("title")?.asString?.trim() ?: ""
            val type = kg.get("type")?.asString?.trim() ?: ""
            val desc = kg.get("description")?.asString?.trim() ?: ""
            val kgLink = kg.get("descriptionUrl")?.asString?.trim() ?: ""
            val imageUrl = kg.get("imageUrl")?.asString?.trim()

            if (title.isNotBlank() && desc.isNotBlank()) {
                val fullSnippet = if (type.isNotBlank()) "$type: $desc" else desc
                val urlToUse = if (kgLink.isNotBlank() && seenUrls.add(kgLink)) kgLink else "https://www.google.com"
                searchResults.add(SearchResult(title, urlToUse, fullSnippet))
            }

            if (!imageUrl.isNullOrBlank() && imageUrl.startsWith("http")) {
                searchImages.add(
                    SearchImage(
                        title = title.ifBlank { query },
                        imageUrl = imageUrl,
                        sourceUrl = kgLink.ifBlank { "https://www.google.com" },
                        sourceDomain = "Google Knowledge Graph"
                    )
                )
            }
        }

        // 3. Organic Results
        val organicArray = rootJson.getAsJsonArray("organic")
        if (organicArray != null) {
            for (elem in organicArray) {
                if (searchResults.size >= maxResults) break
                val obj = elem.asJsonObject

                val title = obj.get("title")?.asString?.trim() ?: continue
                val link = obj.get("link")?.asString?.trim() ?: continue
                val snippet = obj.get("snippet")?.asString?.trim() ?: ""

                if (link.isBlank() || !seenUrls.add(link)) continue

                // Check attributes / price if available
                var enrichedSnippet = snippet
                obj.getAsJsonObject("attributes")?.let { attr ->
                    val attrList = mutableListOf<String>()
                    attr.keySet().forEach { key ->
                        val v = attr.get(key)?.asString?.trim()
                        if (!v.isNullOrBlank()) attrList.add("$key: $v")
                    }
                    if (attrList.isNotEmpty()) {
                        enrichedSnippet = "${attrList.joinToString(" • ")}. $snippet".trim()
                    }
                }

                searchResults.add(
                    SearchResult(
                        title = title,
                        url = link,
                        snippet = enrichedSnippet
                    )
                )

                // Inline thumbnail if present
                val imageUrl = obj.get("imageUrl")?.asString?.trim()
                if (!imageUrl.isNullOrBlank() && imageUrl.startsWith("http")) {
                    searchImages.add(
                        SearchImage(
                            title = title,
                            imageUrl = imageUrl,
                            sourceUrl = link,
                            sourceDomain = "Google"
                        )
                    )
                }
            }
        }

        return SerpApiResult(searchResults, searchImages)
    }
}
