package com.teja.gemmmobile.search

import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.InetAddress
import java.net.URI
import java.net.URL
import java.net.UnknownHostException

private const val TAG = "WebPageFetcher"

/**
 * Result of fetching and parsing a webpage.
 */
data class FetchedPage(
    val url: String,
    val content: String,
    val success: Boolean,
    val errorMessage: String? = null,
    val imageUrl: String? = null,
    val isBlockedOrCaptcha: Boolean = false
)

/**
 * Lightweight, zero-cost on-device HTTP/HTTPS webpage fetcher and plain text extractor.
 * Adheres strictly to security, privacy, and memory guidelines for on-device Android:
 * - Rejects private/local IP targets (SSRF protection with DNS pre-resolution).
 * - Enforces connect/read timeouts from SearchConfig.
 * - Enforces max download size (768 KB) with streaming cap.
 * - Validates every redirect target individually (preventing redirect-based SSRF bypass).
 * - Strips scripts, styles, navigation, footer, cookie banners, and boilerplate HTML.
 * - Decodes HTML entities and normalizes whitespace.
 * - Sentence-boundary length limiting.
 */
open class WebPageFetcher {

    companion object {
        private const val USER_AGENT =
            "Mozilla/5.0 (Linux; Android 14; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile Safari/537.36"

        private val ACCEPTED_CONTENT_TYPES = setOf(
            "text/html",
            "application/xhtml+xml",
            "text/plain"
        )

        // OpenGraph / Twitter Image meta tag patterns for in-app ChatGPT-style image preview
        private val OG_IMAGE_REGEX = Regex(
            """<meta[^>]+(?:property|name)\s*=\s*["'](?:og:image|twitter:image|twitter:image:src)["'][^>]+content\s*=\s*["']([^"']+)["']""",
            RegexOption.IGNORE_CASE
        )
        private val OG_IMAGE_ALT_REGEX = Regex(
            """<meta[^>]+content\s*=\s*["']([^"']+)["'][^>]+(?:property|name)\s*=\s*["'](?:og:image|twitter:image)["']""",
            RegexOption.IGNORE_CASE
        )

        // Cookie banners, GDPR consent dialogs, and tracking overlays
        private val COOKIE_BANNER_REGEX = Regex(
            """<(?:div|section|aside|dialog)[^>]+(?:id|class)=["'][^"']*(?:cookie|consent|gdpr|banner|privacy-bar)[^"']*["'][^>]*>.*?</(?:div|section|aside|dialog)>""",
            setOf(RegexOption.IGNORE_CASE, RegexOption.DOT_MATCHES_ALL)
        )

        // Strip non-content blocks (scripts, styles, svg, noscript, nav, header, footer, aside, forms)
        private val UNWANTED_TAGS_REGEX = Regex(
            """<(script|style|noscript|svg|header|footer|nav|aside|form|template)\b[^>]*>.*?</\1>""",
            setOf(RegexOption.IGNORE_CASE, RegexOption.DOT_MATCHES_ALL)
        )

        // Structural tags that represent line breaks or paragraph dividers
        private val STRUCTURAL_TAGS_REGEX = Regex(
            """<(?:p|div|article|section|h[1-6]|li|tr|br|table|blockquote|pre)\b[^>]*>""",
            RegexOption.IGNORE_CASE
        )

        // All remaining HTML tags
        private val STRIP_ALL_TAGS_REGEX = Regex("""<[^>]+>""")

        // Common HTML entities lookup
        private val COMMON_ENTITIES = mapOf(
            "&nbsp;" to " ",
            "&amp;" to "&",
            "&quot;" to "\"",
            "&apos;" to "'",
            "&#39;" to "'",
            "&lt;" to "<",
            "&gt;" to ">",
            "&ndash;" to "–",
            "&mdash;" to "—",
            "&bull;" to "•",
            "&hellip;" to "…",
            "&copy;" to "©",
            "&reg;" to "®",
            "&trade;" to "™",
            "&lsquo;" to "‘",
            "&rsquo;" to "’",
            "&ldquo;" to "“",
            "&rdquo;" to "”",
            "&cent;" to "¢",
            "&pound;" to "£",
            "&yen;" to "¥",
            "&euro;" to "€"
        )

        private val NUMERIC_DECIMAL_ENTITY_REGEX = Regex("""&#([0-9]{1,7});""")
        private val NUMERIC_HEX_ENTITY_REGEX = Regex("""&#x([0-9a-fA-F]{1,6});""")

        // Indicators of bot-blockers, CAPTCHAs, or authentication walls
        private val CAPTCHA_INDICATORS = listOf(
            "verify you are human",
            "attention required! | cloudflare",
            "please enable javascript and cookies to continue",
            "cf-browser-verification",
            "security check to continue",
            "login required to view this page"
        )
    }

    /**
     * Checks if the given IP address is private, loopback, link-local, multicast, or reserved.
     */
    fun isSafeIp(address: InetAddress): Boolean {
        if (address.isLoopbackAddress ||
            address.isSiteLocalAddress ||
            address.isLinkLocalAddress ||
            address.isMulticastAddress ||
            address.isAnyLocalAddress
        ) {
            return false
        }

        val rawBytes = address.address
        if (rawBytes.size == 4) { // IPv4
            val b0 = rawBytes[0].toInt() and 0xFF
            val b1 = rawBytes[1].toInt() and 0xFF
            // 0.0.0.0/8
            if (b0 == 0) return false
            // 10.0.0.0/8
            if (b0 == 10) return false
            // 127.0.0.0/8
            if (b0 == 127) return false
            // 169.254.0.0/16
            if (b0 == 169 && b1 == 254) return false
            // 172.16.0.0/12 (172.16 - 172.31)
            if (b0 == 172 && b1 in 16..31) return false
            // 192.168.0.0/16
            if (b0 == 192 && b1 == 168) return false
            // 224.0.0.0/4 (Multicast 224-239)
            if (b0 in 224..239) return false
            // 240.0.0.0/4 (Reserved 240-255)
            if (b0 in 240..255) return false
        } else if (rawBytes.size == 16) { // IPv6
            val b0 = rawBytes[0].toInt() and 0xFF
            val b1 = rawBytes[1].toInt() and 0xFF
            // ::1 / loopback or :: unspecified
            if (rawBytes.all { it.toInt() == 0 }) return false
            if (rawBytes.take(15).all { it.toInt() == 0 } && rawBytes[15].toInt() == 1) return false
            // Unique local addresses fc00::/7 (fc or fd)
            if (b0 == 0xFC || b0 == 0xFD) return false
            // Link-local addresses fe80::/10
            if (b0 == 0xFE && (b1 and 0xC0) == 0x80) return false
        }

        return true
    }

    /**
     * Checks if the given URL string has a valid public scheme and hostname format.
     */
    fun isSafeUrl(urlString: String): Boolean {
        if (urlString.isBlank()) return false
        return try {
            val uri = URI(urlString.trim())
            val scheme = uri.scheme?.lowercase()
            if (scheme != "http" && scheme != "https") return false

            val host = uri.host?.lowercase() ?: return false
            if (host.isBlank()) return false
            val cleanHost = host.removePrefix("[").removeSuffix("]")

            // Reject localhost and literal loopback/unspecified addresses
            if (cleanHost == "localhost" || cleanHost == "127.0.0.1" || cleanHost == "0.0.0.0" || cleanHost == "::1" || cleanHost == "::") {
                return false
            }

            // Check literal IPv4 patterns
            val ipv4Parts = cleanHost.split(".")
            if (ipv4Parts.size == 4 && ipv4Parts.all { it.toIntOrNull() in 0..255 }) {
                val octets = ipv4Parts.map { it.toInt() }
                if (octets[0] == 0) return false
                if (octets[0] == 10) return false
                if (octets[0] == 127) return false
                if (octets[0] == 169 && octets[1] == 254) return false
                if (octets[0] == 172 && octets[1] in 16..31) return false
                if (octets[0] == 192 && octets[1] == 168) return false
                if (octets[0] in 224..255) return false
            }

            // Reject explicit IPv6 local representations
            if (cleanHost.startsWith("fe80:") || cleanHost.startsWith("fc00:") || cleanHost.startsWith("fd00:")) {
                return false
            }

            true
        } catch (_: Exception) {
            false
        }
    }

    /**
     * Performs DNS resolution check to prevent DNS-rebinding or domains resolving to private/loopback IPs.
     */
    fun isResolvedHostSafe(host: String): Boolean {
        return try {
            val addresses = InetAddress.getAllByName(host)
            if (addresses.isEmpty()) return false
            addresses.all { isSafeIp(it) }
        } catch (_: UnknownHostException) {
            false
        } catch (_: SecurityException) {
            false
        } catch (_: Exception) {
            false
        }
    }

    /**
     * Decodes HTML entities (both named and numeric decimal/hex).
     */
    fun decodeHtmlEntities(input: String): String {
        var text = input

        // 1. Common named entities
        for ((entity, replacement) in COMMON_ENTITIES) {
            if (text.contains(entity)) {
                text = text.replace(entity, replacement)
            }
        }

        // 2. Numeric decimal entities (e.g. &#160; or &#8212;)
        if (text.contains("&#")) {
            text = NUMERIC_DECIMAL_ENTITY_REGEX.replace(text) { matchResult ->
                val code = matchResult.groupValues[1].toIntOrNull()
                if (code != null && code in 32..65535) {
                    code.toChar().toString()
                } else {
                    ""
                }
            }

            // 3. Numeric hex entities (e.g. &#x2F; or &#x2014;)
            text = NUMERIC_HEX_ENTITY_REGEX.replace(text) { matchResult ->
                val code = matchResult.groupValues[1].toIntOrNull(16)
                if (code != null && code in 32..65535) {
                    code.toChar().toString()
                } else {
                    ""
                }
            }
        }

        return text
    }

    /**
     * Converts raw HTML markup into readable, normalized plain text bounded at sentence boundary.
     */
    fun extractReadableText(html: String, maxChars: Int = SearchConfig.MAX_PAGE_CONTENT_CHARS): String {
        if (html.isBlank()) return ""

        // Check for bot wall or CAPTCHA before extraction
        val lowerHtml = html.lowercase()
        if (CAPTCHA_INDICATORS.any { lowerHtml.contains(it) }) {
            return "" // Signal to rely on search snippet instead of scraping bot wall
        }

        // 1. Remove cookie banners & consent overlays
        var text = COOKIE_BANNER_REGEX.replace(html, "")

        // 2. Remove unwanted script, style, navigation, footer, etc.
        text = UNWANTED_TAGS_REGEX.replace(text, "")

        // 3. Replace structural tags with newline separators
        text = STRUCTURAL_TAGS_REGEX.replace(text, "\n")

        // 4. Strip remaining HTML tags
        text = STRIP_ALL_TAGS_REGEX.replace(text, " ")

        // 5. Decode HTML entities
        text = decodeHtmlEntities(text)

        // 6. Normalize whitespace: trim lines and remove excessive blank lines
        val lines = text.split("\n")
            .map { it.replace(Regex("""[ \t\r\f]+"""), " ").trim() }
            .filter { it.isNotBlank() }

        val normalized = lines.joinToString("\n\n")

        if (normalized.length <= maxChars) {
            return normalized
        }

        // 7. Sentence boundary trimming near maxChars limit
        val cutPoint = findSentenceBoundary(normalized, maxChars)
        return normalized.substring(0, cutPoint).trim() + "…"
    }

    /**
     * Looks for a natural sentence break (. ! ? \n) within a reasonable window before maxChars.
     */
    private fun findSentenceBoundary(text: String, targetLimit: Int): Int {
        if (text.length <= targetLimit) return text.length
        val searchWindowStart = (targetLimit - 400).coerceAtLeast(100)
        val window = text.substring(searchWindowStart, targetLimit)

        // Find last sentence ending punctuation followed by space or newline
        val lastSentenceEnd = window.lastIndexOfAny(charArrayOf('.', '!', '?', '\n'))
        return if (lastSentenceEnd != -1) {
            searchWindowStart + lastSentenceEnd + 1
        } else {
            // Fallback to last whitespace
            val lastSpace = window.lastIndexOf(' ')
            if (lastSpace != -1) {
                searchWindowStart + lastSpace
            } else {
                targetLimit
            }
        }
    }

    /**
     * Extracts OpenGraph or Twitter preview image from HTML head metadata.
     */
    fun extractPrimaryImage(html: String, pageUrl: String): String? {
        val m1 = OG_IMAGE_REGEX.find(html)
        var imgUrl = m1?.groupValues?.get(1)?.trim()
        if (imgUrl.isNullOrBlank()) {
            val m2 = OG_IMAGE_ALT_REGEX.find(html)
            imgUrl = m2?.groupValues?.get(1)?.trim()
        }
        if (imgUrl.isNullOrBlank()) return null

        return try {
            val resolved = URI(pageUrl).resolve(imgUrl).toString()
            if (isSafeUrl(resolved)) resolved else null
        } catch (_: Exception) {
            if (isSafeUrl(imgUrl)) imgUrl else null
        }
    }

    /**
     * Safely downloads public HTML and extracts readable plain text.
     * Manually validates every redirect hop against SSRF and private networks.
     */
    open suspend fun fetchPage(urlString: String): FetchedPage = withContext(Dispatchers.IO) {
        if (!isSafeUrl(urlString)) {
            return@withContext FetchedPage(
                url = urlString,
                content = "",
                success = false,
                errorMessage = "Blocked: Target URL failed safety verification."
            )
        }

        var currentUrl = urlString
        var redirectCount = 0
        var connection: HttpURLConnection? = null

        try {
            while (redirectCount <= SearchConfig.MAX_REDIRECTS) {
                val url = URL(currentUrl)
                val host = url.host ?: return@withContext FetchedPage(urlString, "", false, "Invalid host in target URL")

                // Pre-flight DNS check on host to prevent DNS-rebinding SSRF
                if (!isResolvedHostSafe(host)) {
                    return@withContext FetchedPage(
                        url = urlString,
                        content = "",
                        success = false,
                        errorMessage = "Blocked: Destination host resolves to an unroutable or private IP."
                    )
                }

                connection = (url.openConnection() as HttpURLConnection).apply {
                    requestMethod = "GET"
                    connectTimeout = SearchConfig.CONNECT_TIMEOUT_MS
                    readTimeout = SearchConfig.READ_TIMEOUT_MS
                    instanceFollowRedirects = false // Manual inspection to validate each redirect
                    setRequestProperty("User-Agent", USER_AGENT)
                    setRequestProperty("Accept", "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8")
                    setRequestProperty("Accept-Language", "en-US,en;q=0.9")
                    setRequestProperty("Accept-Encoding", "identity") // Avoid GZIP decompression overhead
                    useCaches = true
                }

                val responseCode = connection.responseCode

                // Handle Redirects Manually
                if (responseCode in 301..308) {
                    redirectCount++
                    if (redirectCount > SearchConfig.MAX_REDIRECTS) {
                        return@withContext FetchedPage(
                            urlString,
                            "",
                            false,
                            "Blocked: Exceeded maximum redirect limit (${SearchConfig.MAX_REDIRECTS})."
                        )
                    }

                    val location = connection.getHeaderField("Location")
                    if (location.isNullOrBlank()) {
                        return@withContext FetchedPage(urlString, "", false, "HTTP redirect without Location header.")
                    }

                    val resolvedUrl = try {
                        URL(url, location).toString()
                    } catch (_: Exception) {
                        return@withContext FetchedPage(urlString, "", false, "Malformed redirect URL: $location")
                    }

                    // Strictly validate the redirect destination
                    if (!isSafeUrl(resolvedUrl)) {
                        return@withContext FetchedPage(
                            urlString,
                            "",
                            false,
                            "Blocked: Redirect target failed safety check: $resolvedUrl"
                        )
                    }

                    currentUrl = resolvedUrl
                    connection.disconnect()
                    continue
                }

                if (responseCode != HttpURLConnection.HTTP_OK) {
                    return@withContext FetchedPage(urlString, "", false, "HTTP $responseCode from server")
                }

                // Verify content type
                val contentTypeHeader = connection.contentType ?: "text/html"
                val mimeType = contentTypeHeader.split(";").first().trim().lowercase()
                if (mimeType !in ACCEPTED_CONTENT_TYPES) {
                    return@withContext FetchedPage(
                        urlString,
                        "",
                        false,
                        "Unsupported MIME type: $mimeType (expected text/html)"
                    )
                }

                // Read up to MAX_PAGE_DOWNLOAD_BYTES with hard streaming limit
                val inputStream = connection.inputStream
                val buffer = CharArray(4096)
                val stringBuilder = StringBuilder()
                val reader = BufferedReader(InputStreamReader(inputStream, Charsets.UTF_8))
                var totalBytesRead = 0

                var charsRead: Int
                while (reader.read(buffer).also { charsRead = it } != -1) {
                    stringBuilder.append(buffer, 0, charsRead)
                    totalBytesRead += charsRead * 2 // UTF-16 approximation
                    if (totalBytesRead >= SearchConfig.MAX_PAGE_DOWNLOAD_BYTES) {
                        Log.d(TAG, "[$TAG] Reached max download cap (${SearchConfig.MAX_PAGE_DOWNLOAD_BYTES} bytes) for $urlString")
                        break
                    }
                }
                reader.close()

                val rawHtml = stringBuilder.toString()
                val readableText = extractReadableText(rawHtml)
                val primaryImage = extractPrimaryImage(rawHtml, currentUrl)

                if (readableText.isBlank()) {
                    return@withContext FetchedPage(
                        urlString,
                        "",
                        false,
                        "Page contains no readable text or is protected by bot wall.",
                        isBlockedOrCaptcha = true
                    )
                }

                return@withContext FetchedPage(
                    url = currentUrl,
                    content = readableText,
                    success = true,
                    imageUrl = primaryImage
                )
            }

            return@withContext FetchedPage(urlString, "", false, "Exceeded maximum redirect limit (${SearchConfig.MAX_REDIRECTS})")
        } catch (t: Throwable) {
            Log.w(TAG, "[$TAG] Failed to fetch $urlString: ${t.localizedMessage}")
            return@withContext FetchedPage(
                url = urlString,
                content = "",
                success = false,
                errorMessage = t.localizedMessage ?: "Network error"
            )
        } finally {
            try {
                connection?.disconnect()
            } catch (_: Exception) {}
        }
    }
}
