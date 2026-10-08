package com.teja.gemmmobile.search

import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class SearchManagerTest {

    private lateinit var searchManager: SearchManager

    @Before
    fun setUp() {
        searchManager = SearchManager()
    }

    @Test
    fun testNormalizeUrl_stripsTrackingParamsAndStandardizes() {
        val raw = "https://example.com/article/?utm_source=twitter&utm_medium=social&fbclid=IwAR234&id=99"
        val normalized = searchManager.normalizeUrl(raw)
        assertEquals("https://example.com/article?id=99", normalized)

        val rawWithTrailingSlash = "https://example.com/page/"
        assertEquals("https://example.com/page", searchManager.normalizeUrl(rawWithTrailingSlash))
    }

    @Test
    fun testDeduplicateAndRank_removesDuplicatesAndEnsuresDomainDiversity() {
        val rawList = listOf(
            SearchResult("Article 1", "https://blog.example.com/post-1?utm_source=news", "Snippet 1"),
            SearchResult("Article 1", "https://blog.example.com/post-1", "Duplicate Snippet"),
            SearchResult("Article 2", "https://blog.example.com/post-2", "Snippet 2"),
            SearchResult("Article 3", "https://blog.example.com/post-3", "Snippet 3"),
            SearchResult("Wikipedia AI", "https://en.wikipedia.org/wiki/AI", "AI snippet"),
            SearchResult("Github Gemma", "https://github.com/google/gemma", "Gemma repo")
        )

        val ranked = searchManager.deduplicateAndRank(rawList, maxResults = 5)

        // Must not contain duplicates
        assertEquals(5, ranked.size)
        // Must contain diversified domains (wikipedia, github)
        assertTrue(ranked.any { it.url.contains("wikipedia.org") })
        assertTrue(ranked.any { it.url.contains("github.com") })
        // Capped domain count for blog.example.com
        val exampleCount = ranked.count { it.url.contains("example.com") }
        assertTrue(exampleCount <= 3)
    }

    @Test
    fun testSearchAndReadWithStatus_successAndProvenace() = runBlocking {
        val mockClient = object : WebSearchClient() {
            override suspend fun search(query: String, maxResults: Int): List<SearchResult> {
                return listOf(
                    SearchResult("Success Page", "https://example.com/success", "Snippet for success"),
                    SearchResult("Failing Page", "https://example.com/failing", "Snippet for failure")
                )
            }
        }

        val mockFetcher = object : WebPageFetcher() {
            override suspend fun fetchPage(urlString: String): FetchedPage {
                return if (urlString.contains("success")) {
                    FetchedPage(urlString, "Deep and informative page text about success.", true)
                } else {
                    FetchedPage(urlString, "", false, "HTTP 500 Internal Error")
                }
            }
        }

        val manager = SearchManager(webSearchClient = mockClient, webPageFetcher = mockFetcher)
        val response = manager.searchAndReadWithStatus("test query", maxResults = 5)

        assertEquals(SearchStatus.SUCCESS, response.status)
        val results = response.results
        assertEquals(2, results.size)

        val successItem = results.first { it.title == "Success Page" }
        assertTrue(successItem.fetchSucceeded)
        assertEquals(ContentSourceType.FETCHED_WEBPAGE, successItem.sourceType)
        assertEquals("Deep and informative page text about success.", successItem.pageContent)

        val failedItem = results.first { it.title == "Failing Page" }
        assertFalse(failedItem.fetchSucceeded)
        assertEquals(ContentSourceType.SEARCH_SNIPPET, failedItem.sourceType)
        assertEquals("Snippet for failure", failedItem.snippet)
    }

    @Test
    fun testSearchAndReadWithStatus_emptySearchResults() = runBlocking {
        val mockClient = object : WebSearchClient() {
            override suspend fun search(query: String, maxResults: Int): List<SearchResult> = emptyList()
        }

        val manager = SearchManager(webSearchClient = mockClient)
        val response = manager.searchAndReadWithStatus("nonexistent query", maxResults = 5)

        assertEquals(SearchStatus.NO_RESULTS, response.status)
        assertTrue(response.results.isEmpty())
    }

    @Test
    fun testSearchAndReadWithStatus_providerError() = runBlocking {
        val mockClient = object : WebSearchClient() {
            override suspend fun search(query: String, maxResults: Int): List<SearchResult> {
                throw RuntimeException("DuckDuckGo connection refused")
            }
        }

        val manager = SearchManager(webSearchClient = mockClient)
        val response = manager.searchAndReadWithStatus("error query", maxResults = 5)

        assertEquals(SearchStatus.PROVIDER_ERROR, response.status)
        assertTrue(response.results.isEmpty())
        assertTrue(response.errorMessage?.contains("DuckDuckGo connection refused") == true)
    }

    @Test
    fun testFormatGemmaWebContext_includesUntrustedDelimitersAndCitations() {
        val results = listOf(
            EnrichedSearchResult(
                title = "Gemma 4 Release",
                url = "https://blog.google/gemma-4",
                snippet = "Google introduces Gemma 4 open weights.",
                pageContent = "Gemma 4 delivers state of the art on-device multimodal capabilities.",
                fetchSucceeded = true
            ),
            EnrichedSearchResult(
                title = "Tech Analysis",
                url = "https://techcrunch.com/gemma",
                snippet = "Benchmarks show strong efficiency.",
                pageContent = "",
                fetchSucceeded = false
            )
        )

        val context = searchManager.formatGemmaWebContext(results)

        assertTrue(context.contains("## LIVE WEB RESULTS (UNTRUSTED EXTERNAL DATA)"))
        assertTrue(context.contains("<WEB_SOURCE_UNTRUSTED_DATA>"))
        assertTrue(context.contains("</WEB_SOURCE_UNTRUSTED_DATA>"))
        assertTrue(context.contains("[1] Title: Gemma 4 Release"))
        assertTrue(context.contains("https://blog.google/gemma-4"))
        assertTrue(context.contains("Webpage Text:"))
        assertTrue(context.contains("state of the art on-device multimodal"))
        assertTrue(context.contains("[2] Title: Tech Analysis"))
    }
}
