package com.teja.gemmmobile.search

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.util.Log
import android.util.LruCache
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.URI
import java.net.URL
import java.util.regex.Pattern

/**
 * Downloads and caches real person profile photos and OpenGraph visual previews.
 * Supports:
 * - GitHub direct avatars: https://github.com/{username}.png
 * - Twitter/X avatars: via unavatar CDN
 * - LinkedIn / Web Profiles / Portfolios: og:image & twitter:image extraction from page <head>
 * - Clean fallback to FaviconLoader when no individual avatar exists
 */
object ProfileAvatarLoader {
    private const val TAG = "ProfileAvatarLoader"
    private val cache = LruCache<String, Bitmap>(60)

    private val OG_IMAGE_PATTERN_1 = Pattern.compile(
        """<meta[^>]+(?:property|name)\s*=\s*["'](?:og:image|twitter:image|twitter:image:src)["'][^>]+content\s*=\s*["']([^"']+)["']""",
        Pattern.CASE_INSENSITIVE
    )
    private val OG_IMAGE_PATTERN_2 = Pattern.compile(
        """<meta[^>]+content\s*=\s*["']([^"']+)["'][^>]+(?:property|name)\s*=\s*["'](?:og:image|twitter:image)["']""",
        Pattern.CASE_INSENSITIVE
    )

    fun getCached(url: String): Bitmap? {
        if (url.isBlank()) return null
        return cache.get(url) ?: FaviconLoader.getCached(url)
    }

    suspend fun loadAvatar(url: String): Bitmap? = withContext(Dispatchers.IO) {
        if (url.isBlank()) return@withContext null

        cache.get(url)?.let { return@withContext it }

        try {
            val lower = url.lowercase()

            // 1. GitHub Direct Profile Photo
            if (lower.contains("github.com/")) {
                val user = url.substringAfter("github.com/").substringBefore("/").substringBefore("?").trim()
                val invalid = setOf("issues", "pull", "explore", "trending", "pricing", "marketplace", "login", "signup", "search", "")
                if (user.isNotBlank() && user !in invalid) {
                    val avatarUrl = "https://github.com/$user.png?size=200"
                    val bmp = downloadBitmap(avatarUrl)
                    if (bmp != null) {
                        cache.put(url, bmp)
                        return@withContext bmp
                    }
                }
            }

            // 2. Twitter / X Direct Avatar
            if (lower.contains("twitter.com/") || lower.contains("x.com/")) {
                val handle = url.substringAfter("twitter.com/").substringAfter("x.com/").substringBefore("/").substringBefore("?").trim()
                if (handle.isNotBlank() && !handle.contains("home") && !handle.contains("status")) {
                    val avatarUrl = "https://unavatar.io/twitter/$handle"
                    val bmp = downloadBitmap(avatarUrl)
                    if (bmp != null) {
                        cache.put(url, bmp)
                        return@withContext bmp
                    }
                }
            }

            // 3. Web Page OpenGraph / Twitter Image meta tag extraction
            val ogImageUrl = extractOgImage(url)
            if (!ogImageUrl.isNullOrBlank()) {
                val resolvedImgUrl = try {
                    URI(url).resolve(ogImageUrl).toString()
                } catch (_: Exception) {
                    ogImageUrl
                }
                val bmp = downloadBitmap(resolvedImgUrl)
                if (bmp != null) {
                    cache.put(url, bmp)
                    return@withContext bmp
                }
            }

            // 4. Fallback to site favicon if no person photo was resolved
            val fallbackFavicon = FaviconLoader.loadFavicon(url)
            if (fallbackFavicon != null) {
                cache.put(url, fallbackFavicon)
                return@withContext fallbackFavicon
            }
        } catch (e: Exception) {
            Log.d(TAG, "[$TAG] Could not load avatar for $url: ${e.message}")
        }

        null
    }

    private fun extractOgImage(pageUrl: String): String? {
        var conn: HttpURLConnection? = null
        try {
            conn = URL(pageUrl).openConnection() as HttpURLConnection
            conn.connectTimeout = 3000
            conn.readTimeout = 3000
            conn.instanceFollowRedirects = true
            conn.requestMethod = "GET"
            conn.setRequestProperty("User-Agent", "Mozilla/5.0 (Linux; Android 14; Mobile; rv:124.0) Gecko/124.0 Firefox/124.0")
            conn.setRequestProperty("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")

            if (conn.responseCode in 200..299) {
                val reader = BufferedReader(InputStreamReader(conn.inputStream))
                val sb = StringBuilder()
                var line: String?
                var bytesRead = 0
                // Read only the first ~40KB (the HTML head section)
                while (reader.readLine().also { line = it } != null) {
                    sb.append(line).append("\n")
                    bytesRead += line!!.length
                    if (bytesRead > 40_000 || sb.contains("</head>", ignoreCase = true)) {
                        break
                    }
                }
                val html = sb.toString()
                val m1 = OG_IMAGE_PATTERN_1.matcher(html)
                if (m1.find()) {
                    return m1.group(1)?.trim()
                }
                val m2 = OG_IMAGE_PATTERN_2.matcher(html)
                if (m2.find()) {
                    return m2.group(1)?.trim()
                }
            }
        } catch (_: Exception) {
            // Ignore fetch errors
        } finally {
            try { conn?.disconnect() } catch (_: Exception) {}
        }
        return null
    }

    private fun downloadBitmap(imgUrl: String): Bitmap? {
        var conn: HttpURLConnection? = null
        try {
            conn = URL(imgUrl).openConnection() as HttpURLConnection
            conn.connectTimeout = 4000
            conn.readTimeout = 4000
            conn.instanceFollowRedirects = true
            conn.requestMethod = "GET"
            conn.setRequestProperty("User-Agent", "Mozilla/5.0 (Linux; Android 14; Mobile)")

            if (conn.responseCode in 200..299) {
                val bytes = conn.inputStream.use { it.readBytes() }
                if (bytes.isNotEmpty()) {
                    val opts = BitmapFactory.Options().apply {
                        inJustDecodeBounds = true
                    }
                    BitmapFactory.decodeByteArray(bytes, 0, bytes.size, opts)

                    // Downsample if image is huge (e.g. > 300px) to save RAM
                    var sampleSize = 1
                    val maxDimension = 240
                    while (opts.outWidth / sampleSize > maxDimension || opts.outHeight / sampleSize > maxDimension) {
                        sampleSize *= 2
                    }

                    val decodeOpts = BitmapFactory.Options().apply {
                        inSampleSize = sampleSize
                    }
                    return BitmapFactory.decodeByteArray(bytes, 0, bytes.size, decodeOpts)
                }
            }
        } catch (_: Exception) {
            // Ignore download errors
        } finally {
            try { conn?.disconnect() } catch (_: Exception) {}
        }
        return null
    }
}
