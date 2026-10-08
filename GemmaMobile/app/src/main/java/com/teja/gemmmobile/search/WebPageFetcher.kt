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
import java.util.regex.Pattern

private const val TAG = "WebPageFetcher"

/**
 * Result of fetching and parsing a webpage.
 */
data class FetchedPage(
    val url: String,
    val content: String,
    val success: Boolean,
    val errorMessage: String? = null,
    val imageUrl: String? = null
)

/**
 * Lightweight, zero-cost on-device HTTP/HTTPS webpage fetcher and plain text extractor.
 * Adheres strictly to security, privacy, and memory guidelines for on-device Android:
 * - Rejects private/local IP targets (SSRF protection).
 * - Enforces connect/read timeouts (3.5s / 4.5s).
 * - Enforces max download size (768 KB).
 * - Strips scripts, styles, navigation, footer, and boilerplate HTML.
 * - Decodes HTML entities and normalizes whitespace.
 * - Sentence-boundary length limiting.
 */
open class WebPageFetcher {

    companion object {
        const val CONNECT_TIMEOUT_MS = 3500
        const val READ_TIMEOUT_MS = 4500
        const val MAX_DOWNLOAD_BYTES = 768 * 1024 // 768 KB
        const val MAX_CONTENT_CHARS = 5000
        const val MAX_REDIRECTS = 4

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
    }

    /**
     * Verifies that the URL is public, uses http/https, and does not target localhost or private RFC1918 subnets.
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

            // Check literal IPv4 patterns for private / link-local addresses
            val ipv4Parts = cleanHost.split(".")
            if (ipv4Parts.size == 4 && ipv4Parts.all { it.toIntOrNull() in 0..255 }) {
                val octets = ipv4Parts.map { it.toInt() }
                // 10.0.0.0/8
                if (octets[0] == 10) return false
                // 127.0.0.0/8
                if (octets[0] == 127) return false
                // 169.254.0.0/16
                if (octets[0] == 169 && octets[1] == 254) return false
                // 172.16.0.0/12 (172.16 to 172.31)
                if (octets[0] == 172 && octets[1] in 16..31) return false
                // 192.168.0.0/16
                if (octets[0] == 192 && octets[1] == 168) return false
                // 0.0.0.0/8
                if (octets[0] == 0) return false
            }

            // Reject IPv6 local addresses
            if (cleanHost.startsWith("fe80:") || cleanHost.startsWith("fc00:") || cleanHost.startsWith("fd00:")) {
                return false
            }

            true
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
    fun extractReadableText(html: String, maxChars: Int = MAX_CONTENT_CHARS): String {
        if (html.isBlank()) return ""

        // 1. Remove unwanted script, style, navigation, footer, etc.
        var text = UNWANTED_TAGS_REGEX.replace(html, "")

        // 2. Replace structural tags with newline separators
        text = STRUCTURAL_TAGS_REGEX.replace(text, "\n")

        // 3. Strip remaining HTML tags
        text = STRIP_ALL_TAGS_REGEX.replace(text, " ")

        // 4. Decode HTML entities
        text = decodeHtmlEntities(text)

        // 5. Normalize whitespace: trim lines and remove excessive blank lines
        val lines = text.split("\n")
            .map { it.replace(Regex("""[ \t\r\f]+"""), " ").trim() }
            .filter { it.isNotBlank() }

        val normalized = lines.joinToString("\n\n")

        if (normalized.length <= maxChars) {
            return normalized
        }

        // 6. Sentence boundary trimming near maxChars limit
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
     */
    open suspend fun fetchPage(urlString: String): FetchedPage = withContext(Dispatchers.IO) {
        if (!isSafeUrl(urlString)) {
            return@withContext FetchedPage(
                url = urlString,
                content = "",
                success = false,
                errorMessage = "Blocked: Invalid or unsafe target URL."
            )
        }

        var currentUrl = urlString
        var redirectCount = 0
        var connection: HttpURLConnection? = null

        try {
            while (redirectCount < MAX_REDIRECTS) {
                val url = URL(currentUrl)
                connection = (url.openConnection() as HttpURLConnection).apply {
                    requestMethod = "GET"
                    connectTimeout = CONNECT_TIMEOUT_MS
                    readTimeout = READ_TIMEOUT_MS
                    instanceFollowRedirects = false // Manual inspection to validate destination
                    setRequestProperty("User-Agent", USER_AGENT)
                    setRequestProperty("Accept", "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8")
                    setRequestProperty("Accept-Language", "en-US,en;q=0.9,te;q=0.8")
                    setRequestProperty("Accept-Encoding", "identity") // Avoid GZIP decompression overhead
                    useCaches = true
                }

                val responseCode = connection.responseCode
                if (responseCode in 301..308) {
                    val location = connection.getHeaderField("Location")
                    if (location.isNullOrBlank()) {
                        return@withContext FetchedPage(urlString, "", false, "HTTP redirect without Location header")
                    }

                    val resolvedUrl = try {
                        URL(url, location).toString()
                    } catch (_: Exception) {
                        return@withContext FetchedPage(urlString, "", false, "Malformed redirect URL: $location")
                    }

                    if (!isSafeUrl(resolvedUrl)) {
                        return@withContext FetchedPage(urlString, "", false, "Redirect target is unsafe: $resolvedUrl")
                    }

                    currentUrl = resolvedUrl
                    redirectCount++
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

                // Read up to MAX_DOWNLOAD_BYTES
                val inputStream = connection.inputStream
                val buffer = CharArray(4096)
                val stringBuilder = StringBuilder()
                val reader = BufferedReader(InputStreamReader(inputStream, Charsets.UTF_8))
                var totalBytesRead = 0

                var charsRead: Int
                while (reader.read(buffer).also { charsRead = it } != -1) {
                    stringBuilder.append(buffer, 0, charsRead)
                    totalBytesRead += charsRead * 2 // UTF-16 approximation
                    if (totalBytesRead >= MAX_DOWNLOAD_BYTES) {
                        Log.d(TAG, "[$TAG] Reached max download cap ($MAX_DOWNLOAD_BYTES bytes) for $urlString")
                        break
                    }
                }
                reader.close()

                val rawHtml = stringBuilder.toString()
                val readableText = extractReadableText(rawHtml)
                val primaryImage = extractPrimaryImage(rawHtml, currentUrl)

                if (readableText.isBlank()) {
                    return@withContext FetchedPage(urlString, "", false, "Page contains no readable text content.")
                }

                return@withContext FetchedPage(
                    url = currentUrl,
                    content = readableText,
                    success = true,
                    imageUrl = primaryImage
                )
            }

            return@withContext FetchedPage(urlString, "", false, "Exceeded maximum redirect limit ($MAX_REDIRECTS)")
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
