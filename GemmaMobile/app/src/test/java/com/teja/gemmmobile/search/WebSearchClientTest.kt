package com.teja.gemmmobile.search

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class WebSearchClientTest {

    private lateinit var client: WebSearchClient

    @Before
    fun setUp() {
        client = WebSearchClient()
    }

    @Test
    fun testSanitizeQuery_stripsPrefixesAndTeluguFillers() {
        assertEquals("quantum computing", client.sanitizeQuery("search the web for quantum computing"))
        assertEquals("Sundar Pichai", client.sanitizeQuery("who is Sundar Pichai"))
        assertEquals("Blackwell GPU", client.sanitizeQuery("Google for Blackwell GPU"))
        assertEquals("Gemma 4", client.sanitizeQuery("Gemma 4 gurinchi cheppu"))
        assertEquals("Quantum physics", client.sanitizeQuery("Quantum physics in telugu"))
        assertEquals("tulasi teja pampana", client.sanitizeQuery("search who is tulasi teja pampana"))
        assertEquals("spacex starship", client.sanitizeQuery("can you please search the web for spacex starship?"))
    }

    @Test
    fun testDecodeBingUrl_decodesBase64TrackingUrl() {
        // Base64 encoding of "https://en.wikipedia.org/wiki/Quantum" is "aHR0cHM6Ly9lbi53aWtpcGVkaWEub3JnL3dpa2kvUXVhbnR1bQ"
        val bingTrackingUrl = "https://www.bing.com/ck/a?!&&p=123&u=a1aHR0cHM6Ly9lbi53aWtpcGVkaWEub3JnL3dpa2kvUXVhbnR1bQ&ntb=1"
        val decoded = client.decodeBingUrl(bingTrackingUrl)
        assertEquals("https://en.wikipedia.org/wiki/Quantum", decoded)

        // Normal direct URL remains unchanged
        val directUrl = "https://example.com/direct/page"
        assertEquals("https://example.com/direct/page", client.decodeBingUrl(directUrl))
    }

    @Test
    fun testParseBingSearchResults_extractsTitlesUrlsAndSnippets() {
        val sampleHtml = """
            <ol id="b_results">
              <li class="b_algo">
                <h2><a href="https://www.bing.com/ck/a?!&amp;u=a1aHR0cHM6Ly9leGFtcGxlLmNvbS9hcnRpY2xl&amp;ntb=1"><strong>Quantum</strong> Leap in AI</a></h2>
                <div class="b_caption"><p>Researchers announced a breakthrough in hybrid quantum neural networks today.</p></div>
              </li>
              <li class="b_algo">
                <h2><a href="https://raw.example.org/simple">Simple Title &amp; More</a></h2>
                <div class="b_caption"><p>Another detailed snippet explaining quantum algorithms.</p></div>
              </li>
            </ol>
        """.trimIndent()

        val results = client.parseBingSearchResults(sampleHtml, maxResults = 5)
        assertEquals(2, results.size)

        assertEquals("Quantum Leap in AI", results[0].title)
        assertEquals("https://example.com/article", results[0].url)
        assertEquals("Researchers announced a breakthrough in hybrid quantum neural networks today.", results[0].snippet)

        assertEquals("Simple Title & More", results[1].title)
        assertEquals("https://raw.example.org/simple", results[1].url)
        assertEquals("Another detailed snippet explaining quantum algorithms.", results[1].snippet)
    }

    @Test
    fun testParseDdgLite_extractsTitlesUrlsAndSnippets() {
        val sampleLiteHtml = """
            <table>
              <tr>
                <td><a class="result-link" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fen.wikipedia.org%2Fwiki%2FS._S._Rajamouli&rut=1">S. S. Rajamouli - Wikipedia</a></td>
              </tr>
              <tr>
                <td class="result-snippet">S. S. Rajamouli is an Indian filmmaker who primarily works in Telugu cinema.</td>
              </tr>
              <tr>
                <td><a class="result-link" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.imdb.com%2Fname%2Fnm1442514%2F&rut=1">S.S. Rajamouli - IMDb</a></td>
              </tr>
              <tr>
                <td class="result-snippet">Director: RRR, Baahubali. Indian filmmaker known worldwide.</td>
              </tr>
            </table>
        """.trimIndent()

        val results = client.parseDdgLite(sampleLiteHtml, maxResults = 5)
        assertEquals(2, results.size)
        assertEquals("S. S. Rajamouli - Wikipedia", results[0].title)
        assertEquals("https://en.wikipedia.org/wiki/S._S._Rajamouli", results[0].url)
        assertEquals("S. S. Rajamouli is an Indian filmmaker who primarily works in Telugu cinema.", results[0].snippet)

        assertEquals("S.S. Rajamouli - IMDb", results[1].title)
        assertEquals("https://www.imdb.com/name/nm1442514/", results[1].url)
    }
}
