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

        val manager = SearchManager(
            webSearchClient = mockClient,
            webPageFetcher = mockFetcher,
            serpApiClient = SerpApiClient(""),
            serperClient = SerperClient("")
        )
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

        val manager = SearchManager(
            webSearchClient = mockClient,
            serpApiClient = SerpApiClient(""),
            serperClient = SerperClient("")
        )
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

        val manager = SearchManager(
            webSearchClient = mockClient,
            serpApiClient = SerpApiClient(""),
            serperClient = SerperClient("")
        )
        val response = manager.searchAndReadWithStatus("error query", maxResults = 5)

        assertEquals(SearchStatus.PROVIDER_ERROR, response.status)
        assertTrue(response.results.isEmpty())
        assertTrue(response.errorMessage?.contains("DuckDuckGo connection refused") == true)
    }

    @Test
    fun testSearchAndReadWithStatus_serperPrimarySuccess() = runBlocking {
        val mockSerper = object : SerperClient("dummy-key") {
            override suspend fun search(query: String, maxResults: Int, isProduct: Boolean): SerpApiResult {
                return SerpApiResult(
                    results = listOf(
                        SearchResult("Dot & Key Sunscreen", "https://amazon.in/dp/123", "₹224 on Amazon.in.")
                    ),
                    images = listOf(
                        SearchImage("Dot & Key Sunscreen", "https://img.com/dotkey.jpg", "https://amazon.in/dp/123", "Amazon.in")
                    )
                )
            }
        }

        val manager = SearchManager(serperClient = mockSerper, serpApiClient = SerpApiClient(""))
        val response = manager.searchAndReadWithStatus("dot and key sunscreen", maxResults = 5, isProduct = true)

        assertEquals(SearchStatus.SUCCESS, response.status)
        assertEquals(1, response.results.size)
        assertEquals("Dot & Key Sunscreen", response.results[0].title)
        assertEquals(1, response.images.size)
        assertEquals("https://img.com/dotkey.jpg", response.images[0].imageUrl)
    }

    @Test
    fun testSearchAndReadWithStatus_serpApiBackupSuccess() = runBlocking {
        val mockSerp = object : SerpApiClient("dummy-key") {
            override suspend fun search(query: String, maxResults: Int, isProduct: Boolean): SerpApiResult {
                return SerpApiResult(
                    results = listOf(
                        SearchResult("Realme P4 5G", "https://www.google.com/search?ibp=oshop&prds=catalogid:123", "₹18,499 on Reliance Digital.")
                    ),
                    images = listOf(
                        SearchImage("Realme P4 5G", "https://img.com/thumb.jpg", "https://reliancedigital.in/p4", "Reliance Digital")
                    )
                )
            }
        }

        val manager = SearchManager(serperClient = SerperClient(""), serpApiClient = mockSerp)
        val response = manager.searchAndReadWithStatus("best phone under 20000", maxResults = 5, isProduct = true)

        assertEquals(SearchStatus.SUCCESS, response.status)
        assertEquals(1, response.results.size)
        assertEquals("Realme P4 5G", response.results[0].title)
        assertEquals(1, response.images.size)
        assertEquals("https://img.com/thumb.jpg", response.images[0].imageUrl)
    }

    @Test
    fun testSearchAndReadWithStatus_nonProductDoesNotUseSerperOrSerpApi() = runBlocking {
        var serperCalled = false
        var serpApiCalled = false

        val mockSerper = object : SerperClient("dummy-key") {
            override suspend fun search(query: String, maxResults: Int, isProduct: Boolean): SerpApiResult {
                serperCalled = true
                return SerpApiResult(emptyList(), emptyList())
            }
        }

        val mockSerp = object : SerpApiClient("dummy-key") {
            override suspend fun search(query: String, maxResults: Int, isProduct: Boolean): SerpApiResult {
                serpApiCalled = true
                return SerpApiResult(emptyList(), emptyList())
            }
        }

        val mockWebClient = object : WebSearchClient() {
            override suspend fun search(query: String, maxResults: Int): List<SearchResult> {
                return listOf(SearchResult("Free Wikipedia Article", "https://en.wikipedia.org/wiki/India", "Free snippet"))
            }
        }

        val manager = SearchManager(
            webSearchClient = mockWebClient,
            serperClient = mockSerper,
            serpApiClient = mockSerp
        )

        val response = manager.searchAndReadWithStatus("tell me about India history", maxResults = 5, isProduct = false)

        assertEquals(SearchStatus.SUCCESS, response.status)
        assertFalse("Serper must NOT be called for non-product general searches!", serperCalled)
        assertFalse("SerpApi must NOT be called for non-product general searches!", serpApiCalled)
        assertEquals("Free Wikipedia Article", response.results[0].title)
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
        assertTrue(context.contains("[2] Title: Tech Analysis"))
    }

    @Test
    fun testParseBingImages_extractsHighResImagesAndValidatesUrls() {
        val sampleHtml = """
            <div class="dg_u">
              <a class="iusc" m="{&quot;murl&quot;:&quot;https://cdn.example.com/images/jwst.jpg&quot;,&quot;t&quot;:&quot;James Webb Space Telescope Deep Field&quot;,&quot;purl&quot;:&quot;https://nasa.gov/jwst&quot;}"></a>
              <a class="iusc" m="{&quot;murl&quot;:&quot;https://cdn.example.com/images/earth.png&quot;,&quot;t&quot;:&quot;Planet Earth from Orbit&quot;,&quot;purl&quot;:&quot;https://nasa.gov/earth&quot;}"></a>
              <!-- Private/unsafe IP image that should be rejected by SSRF filter -->
              <a class="iusc" m="{&quot;murl&quot;:&quot;http://127.0.0.1/secret.jpg&quot;,&quot;t&quot;:&quot;Internal&quot;,&quot;purl&quot;:&quot;http://127.0.0.1&quot;}"></a>
            </div>
        """.trimIndent()

        val parsed = searchManager.parseBingImages(sampleHtml, limit = 5, defaultTitle = "Fallback")
        assertEquals(2, parsed.size)

        assertEquals("James Webb Space Telescope Deep Field", parsed[0].title)
        assertEquals("https://cdn.example.com/images/jwst.jpg", parsed[0].imageUrl)
        assertEquals("https://nasa.gov/jwst", parsed[0].sourceUrl)
        assertEquals("nasa.gov", parsed[0].sourceDomain)

        assertEquals("Planet Earth from Orbit", parsed[1].title)
        assertEquals("https://cdn.example.com/images/earth.png", parsed[1].imageUrl)
    }
}
