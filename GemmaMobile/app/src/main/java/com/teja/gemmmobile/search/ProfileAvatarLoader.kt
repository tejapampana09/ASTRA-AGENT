package com.teja.gemmmobile.search

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.util.Log
import android.util.LruCache
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.BufferedReader
import java.io.ByteArrayOutputStream
import java.io.InputStream
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.URI
import java.net.URL
import java.util.regex.Pattern

/**
 * Downloads and caches person profile photos and OpenGraph visual previews.
 * Features strict memory bounds, streaming size limits, inSampleSize decodes, and timeout protection.
 *
 * Supports:
 * - GitHub direct avatars: https://github.com/{username}.png
 * - Twitter/X avatars: via unavatar CDN
 * - High-confidence author/profile meta extraction
 * - OpenGraph/Twitter image fallback
 * - Clean favicon fallback as last resort
 */
object ProfileAvatarLoader {
    private const val TAG = "ProfileAvatarLoader"
    private val avatarCache = LruCache<String, Bitmap>(60)
    private val imageCache = LruCache<String, Bitmap>(40)

    private val PROFILE_IMAGE_PATTERN = Pattern.compile(
        """<meta[^>]+(?:property|name)\s*=\s*["'](?:profile:image|author:image|twitter:image)["'][^>]+content\s*=\s*["']([^"']+)["']""",
        Pattern.CASE_INSENSITIVE
    )

    private val OG_IMAGE_PATTERN_1 = Pattern.compile(
        """<meta[^>]+(?:property|name)\s*=\s*["'](?:og:image|twitter:image:src)["'][^>]+content\s*=\s*["']([^"']+)["']""",
        Pattern.CASE_INSENSITIVE
    )

    private val OG_IMAGE_PATTERN_2 = Pattern.compile(
        """<meta[^>]+content\s*=\s*["']([^"']+)["'][^>]+(?:property|name)\s*=\s*["'](?:og:image)["']""",
        Pattern.CASE_INSENSITIVE
    )

    fun getCached(url: String): Bitmap? {
        if (url.isBlank()) return null
        return avatarCache.get(url) ?: FaviconLoader.getCached(url)
    }

    fun getCachedImage(url: String): Bitmap? {
        if (url.isBlank()) return null
        return imageCache.get(url)
    }

    suspend fun loadAvatar(url: String): Bitmap? = withContext(Dispatchers.IO) {
        if (url.isBlank()) return@withContext null

        avatarCache.get(url)?.let { return@withContext it }

        try {
            val lower = url.lowercase()

            // 1. High-confidence: GitHub Direct Profile Photo
            if (lower.contains("github.com/")) {
                val user = url.substringAfter("github.com/").substringBefore("/").substringBefore("?").trim()
                val invalid = setOf("issues", "pull", "explore", "trending", "pricing", "marketplace", "login", "signup", "search", "")
                if (user.isNotBlank() && user !in invalid) {
                    val avatarUrl = "https://github.com/$user.png?size=200"
                    val bmp = downloadBitmap(avatarUrl, maxBytes = SearchConfig.MAX_AVATAR_DOWNLOAD_BYTES, maxDimension = SearchConfig.MAX_AVATAR_DIMENSION)
                    if (bmp != null) {
                        avatarCache.put(url, bmp)
                        return@withContext bmp
                    }
                }
            }

            // 2. High-confidence: Twitter / X Direct Avatar
            if (lower.contains("twitter.com/") || lower.contains("x.com/")) {
                val handle = url.substringAfter("twitter.com/").substringAfter("x.com/").substringBefore("/").substringBefore("?").trim()
                if (handle.isNotBlank() && !handle.contains("home") && !handle.contains("status")) {
                    val avatarUrl = "https://unavatar.io/twitter/$handle"
                    val bmp = downloadBitmap(avatarUrl, maxBytes = SearchConfig.MAX_AVATAR_DOWNLOAD_BYTES, maxDimension = SearchConfig.MAX_AVATAR_DIMENSION)
                    if (bmp != null) {
                        avatarCache.put(url, bmp)
                        return@withContext bmp
                    }
                }
            }

            // 3. Medium-confidence: Profile or OpenGraph image from page <head>
            val extractedImgUrl = extractProfileOrOgImage(url)
            if (!extractedImgUrl.isNullOrBlank()) {
                val resolvedImgUrl = try {
                    URI(url).resolve(extractedImgUrl).toString()
                } catch (_: Exception) {
                    extractedImgUrl
                }
                val bmp = downloadBitmap(resolvedImgUrl, maxBytes = SearchConfig.MAX_AVATAR_DOWNLOAD_BYTES, maxDimension = SearchConfig.MAX_AVATAR_DIMENSION)
                if (bmp != null) {
                    avatarCache.put(url, bmp)
                    return@withContext bmp
                }
            }

            // 4. Low-confidence fallback: Favicon of the site
            val fallbackFavicon = FaviconLoader.loadFavicon(url)
            if (fallbackFavicon != null) {
                avatarCache.put(url, fallbackFavicon)
                return@withContext fallbackFavicon
            }
        } catch (e: Exception) {
            Log.d(TAG, "[$TAG] Could not load avatar for $url: ${e.message}")
        }

        null
    }

    suspend fun loadImage(imgUrl: String): Bitmap? = withContext(Dispatchers.IO) {
        if (imgUrl.isBlank()) return@withContext null
        imageCache.get(imgUrl)?.let { return@withContext it }
        val bmp = downloadBitmap(
            imgUrl,
            maxBytes = SearchConfig.MAX_IMAGE_DOWNLOAD_BYTES,
            maxDimension = SearchConfig.MAX_BITMAP_DIMENSION
        )
        if (bmp != null) {
            imageCache.put(imgUrl, bmp)
        }
        bmp
    }

    /**
     * Extracts profile image or OG image from the head section of a webpage.
     */
    private fun extractProfileOrOgImage(pageUrl: String): String? {
        var conn: HttpURLConnection? = null
        try {
            conn = URL(pageUrl).openConnection() as HttpURLConnection
            conn.connectTimeout = SearchConfig.IMAGE_CONNECT_TIMEOUT_MS
            conn.readTimeout = SearchConfig.IMAGE_READ_TIMEOUT_MS
            conn.instanceFollowRedirects = true
            conn.requestMethod = "GET"
            conn.setRequestProperty("User-Agent", "Mozilla/5.0 (Linux; Android 14; Mobile)")
            conn.setRequestProperty("Accept", "text/html,application/xhtml+xml;q=0.9")

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

                // Check profile-specific pattern first
                val pMatch = PROFILE_IMAGE_PATTERN.matcher(html)
                if (pMatch.find()) {
                    return pMatch.group(1)?.trim()
                }

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

    /**
     * Downloads and decodes a bitmap with strict byte caps, content-type verification,
     * and inSampleSize downsampling to prevent OutOfMemoryError.
     */
    fun downloadBitmap(
        imgUrl: String,
        maxBytes: Int = SearchConfig.MAX_IMAGE_DOWNLOAD_BYTES,
        maxDimension: Int = SearchConfig.MAX_BITMAP_DIMENSION
    ): Bitmap? {
        var conn: HttpURLConnection? = null
        try {
            conn = URL(imgUrl).openConnection() as HttpURLConnection
            conn.connectTimeout = SearchConfig.IMAGE_CONNECT_TIMEOUT_MS
            conn.readTimeout = SearchConfig.IMAGE_READ_TIMEOUT_MS
            conn.instanceFollowRedirects = true
            conn.requestMethod = "GET"
            conn.setRequestProperty("User-Agent", "Mozilla/5.0 (Linux; Android 14; Mobile)")
            conn.setRequestProperty("Accept", "image/webp,image/png,image/jpeg,image/*;q=0.8")

            if (conn.responseCode !in 200..299) {
                return null
            }

            // 1. Content-Type check: must be an image
            val contentType = conn.contentType?.lowercase() ?: ""
            if (contentType.isNotEmpty() && !contentType.startsWith("image/") && !contentType.contains("octet-stream")) {
                Log.d(TAG, "[$TAG] Rejected non-image content type: $contentType for $imgUrl")
                return null
            }

            // 2. Content-Length check: reject if advertised as oversized
            val contentLength = conn.contentLength
            if (contentLength > maxBytes) {
                Log.w(TAG, "[$TAG] Rejected oversized image: $contentLength bytes > $maxBytes cap for $imgUrl")
                return null
            }

            // 3. Streaming read with strict byte limit
            val inputStream: InputStream = conn.inputStream
            val byteBuffer = ByteArrayOutputStream()
            val chunk = ByteArray(4096)
            var totalRead = 0
            var bytesRead: Int

            while (inputStream.read(chunk).also { bytesRead = it } != -1) {
                byteBuffer.write(chunk, 0, bytesRead)
                totalRead += bytesRead
                if (totalRead > maxBytes) {
                    Log.w(TAG, "[$TAG] Image exceeded streaming cap ($maxBytes bytes), aborting download of $imgUrl")
                    return null
                }
            }
            inputStream.close()

            val bytes = byteBuffer.toByteArray()
            if (bytes.isEmpty()) return null

            // 4. Memory-safe decoding with inSampleSize
            val boundsOpts = BitmapFactory.Options().apply {
                inJustDecodeBounds = true
            }
            BitmapFactory.decodeByteArray(bytes, 0, bytes.size, boundsOpts)

            if (boundsOpts.outWidth <= 0 || boundsOpts.outHeight <= 0) {
                return null // Malformed image
            }

            var sampleSize = 1
            while (boundsOpts.outWidth / sampleSize > maxDimension || boundsOpts.outHeight / sampleSize > maxDimension) {
                sampleSize *= 2
            }

            val decodeOpts = BitmapFactory.Options().apply {
                inSampleSize = sampleSize
                inPreferredConfig = Bitmap.Config.RGB_565 // 2 bytes per pixel instead of 4 for 50% RAM reduction
            }

            return try {
                BitmapFactory.decodeByteArray(bytes, 0, bytes.size, decodeOpts)
            } catch (oom: OutOfMemoryError) {
                Log.e(TAG, "[$TAG] OOM while decoding bitmap for $imgUrl", oom)
                System.gc()
                null
            }
        } catch (_: Exception) {
            // Ignore download and parse errors
        } finally {
            try { conn?.disconnect() } catch (_: Exception) {}
        }
        return null
    }
}
