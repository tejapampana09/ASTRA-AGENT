package com.teja.gemmmobile.search

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.net.InetAddress

class WebPageFetcherTest {

    private lateinit var fetcher: WebPageFetcher

    @Before
    fun setUp() {
        fetcher = WebPageFetcher()
    }

    @Test
    fun testExtractReadableText_stripsScriptsStylesAndBoilerplate() {
        val html = """
            <!DOCTYPE html>
            <html>
            <head>
                <style>body { color: red; } .nav { display: none; }</style>
                <script>function track() { console.log('tracking'); }</script>
            </head>
            <body>
                <header><h1>Site Header</h1><nav><a href="/">Home</a></nav></header>
                <article>
                    <p>This is the actual article content that should be preserved.</p>
                </article>
                <aside>Related stories</aside>
                <footer>Copyright 2026 Example Corp</footer>
            </body>
            </html>
        """.trimIndent()

        val extracted = fetcher.extractReadableText(html)
        assertTrue(extracted.contains("This is the actual article content that should be preserved."))
        assertFalse(extracted.contains("color: red"))
        assertFalse(extracted.contains("tracking"))
        assertFalse(extracted.contains("Site Header"))
        assertFalse(extracted.contains("Copyright 2026 Example Corp"))
        assertFalse(extracted.contains("Related stories"))
    }

    @Test
    fun testExtractReadableText_stripsCookieBannersAndConsentOverlays() {
        val html = """
            <div id="cookie-consent-banner" class="cookie-notice">
                <p>We use cookies to improve your experience. Accept all cookies.</p>
                <button>Accept</button>
            </div>
            <article>
                <p>Essential factual content that must remain.</p>
            </article>
        """.trimIndent()

        val extracted = fetcher.extractReadableText(html)
        assertTrue(extracted.contains("Essential factual content that must remain."))
        assertFalse(extracted.contains("We use cookies to improve your experience"))
        assertFalse(extracted.contains("Accept all cookies"))
    }

    @Test
    fun testExtractReadableText_detectsCaptchaAndBotWalls() {
        val captchaHtml = """
            <html>
            <body>
                <h1>Attention Required! | Cloudflare</h1>
                <p>Please enable JavaScript and cookies to continue. Verify you are human to proceed.</p>
            </body>
            </html>
        """.trimIndent()

        val extracted = fetcher.extractReadableText(captchaHtml)
        assertTrue(extracted.isEmpty())
    }

    @Test
    fun testExtractReadableText_convertsStructuralTagsToLineBreaks() {
        val html = """
            <div>First section header</div>
            <p>First paragraph with informative details.</p>
            <ul>
                <li>Item Alpha</li>
                <li>Item Beta</li>
            </ul>
            <br>
            <p>Final concluding sentence.</p>
        """.trimIndent()

        val extracted = fetcher.extractReadableText(html)
        assertTrue(extracted.contains("First section header"))
        assertTrue(extracted.contains("First paragraph with informative details."))
        assertTrue(extracted.contains("Item Alpha"))
        assertTrue(extracted.contains("Item Beta"))
        assertTrue(extracted.contains("Final concluding sentence."))
        assertTrue(extracted.contains("\n"))
    }

    @Test
    fun testExtractReadableText_handlesMalformedHtml() {
        val malformed = "<p>Unclosed paragraph <div>Nested unclosed <span>Text here</b></i></p>"
        val extracted = fetcher.extractReadableText(malformed)
        assertTrue(extracted.contains("Unclosed paragraph"))
        assertTrue(extracted.contains("Text here"))
    }

    @Test
    fun testDecodeHtmlEntities_namedAndNumeric() {
        val input = "AT&amp;T &quot;Rock &amp; Roll&quot; &lt;tag&gt; &#39;quotes&#39; 100&nbsp;USD &ndash; &#8212; &#x2F;"
        val decoded = fetcher.decodeHtmlEntities(input)

        assertTrue(decoded.contains("AT&T"))
        assertTrue(decoded.contains("\"Rock & Roll\""))
        assertTrue(decoded.contains("<tag>"))
        assertTrue(decoded.contains("'quotes'"))
        assertTrue(decoded.contains("100 USD"))
        assertTrue(decoded.contains("–"))
        assertTrue(decoded.contains("—"))
        assertTrue(decoded.contains("/"))
    }

    @Test
    fun testExtractReadableText_respectsSentenceBoundaryCapping() {
        val sentence1 = "The James Webb Space Telescope has observed distant galaxies from the dawn of time. "
        val sentence2 = "These galaxies are brighter than theoretical models predicted. "
        val sentence3 = "Scientists continue to study cosmological formations across the universe. "
        val longHtml = "<p>" + sentence1.repeat(20) + sentence2.repeat(20) + sentence3.repeat(20) + "</p>"

        val maxCap = 250
        val extracted = fetcher.extractReadableText(longHtml, maxChars = maxCap)

        assertTrue(extracted.length <= maxCap + 3)
        assertTrue(extracted.endsWith("…"))
        val withoutEllipsis = extracted.removeSuffix("…").trim()
        assertTrue(withoutEllipsis.endsWith("."))
    }

    @Test
    fun testIsSafeUrl_validPublicUrls() {
        assertTrue(fetcher.isSafeUrl("https://en.wikipedia.org/wiki/Artificial_intelligence"))
        assertTrue(fetcher.isSafeUrl("https://github.com/google/gemma.cpp"))
        assertTrue(fetcher.isSafeUrl("http://example.com/blog/article?id=123"))
        assertTrue(fetcher.isSafeUrl("https://news.ycombinator.com/item?id=4000000"))
    }

    @Test
    fun testIsSafeUrl_rejectsSsrfAndLocalTargets() {
        assertFalse(fetcher.isSafeUrl("http://localhost:8080/admin"))
        assertFalse(fetcher.isSafeUrl("http://127.0.0.1:3000/secret"))
        assertFalse(fetcher.isSafeUrl("http://0.0.0.0/"))
        assertFalse(fetcher.isSafeUrl("http://[::1]/"))
        assertFalse(fetcher.isSafeUrl("http://10.0.0.1/internal"))
        assertFalse(fetcher.isSafeUrl("http://192.168.1.1/router"))
        assertFalse(fetcher.isSafeUrl("http://172.16.0.1/private"))
        assertFalse(fetcher.isSafeUrl("http://172.31.255.255/private"))
        assertFalse(fetcher.isSafeUrl("http://169.254.169.254/latest/meta-data"))
        assertFalse(fetcher.isSafeUrl("file:///data/user/0/com.teja.gemmmobile/databases/chat.db"))
        assertFalse(fetcher.isSafeUrl("ftp://ftp.funet.fi/pub/"))
        assertFalse(fetcher.isSafeUrl("javascript:alert('xss')"))
        assertFalse(fetcher.isSafeUrl(""))
    }

    @Test
    fun testIsSafeIp_rejectsPrivateAndLoopbackIps() {
        assertFalse(fetcher.isSafeIp(InetAddress.getByName("127.0.0.1")))
        assertFalse(fetcher.isSafeIp(InetAddress.getByName("10.0.0.1")))
        assertFalse(fetcher.isSafeIp(InetAddress.getByName("172.16.0.1")))
        assertFalse(fetcher.isSafeIp(InetAddress.getByName("172.31.1.1")))
        assertFalse(fetcher.isSafeIp(InetAddress.getByName("192.168.1.1")))
        assertFalse(fetcher.isSafeIp(InetAddress.getByName("169.254.169.254")))
        assertFalse(fetcher.isSafeIp(InetAddress.getByName("0.0.0.0")))
        assertFalse(fetcher.isSafeIp(InetAddress.getByName("::1")))

        // Valid public IP addresses
        assertTrue(fetcher.isSafeIp(InetAddress.getByName("8.8.8.8")))
        assertTrue(fetcher.isSafeIp(InetAddress.getByName("1.1.1.1")))
        assertTrue(fetcher.isSafeIp(InetAddress.getByName("142.250.190.46")))
    }
}
