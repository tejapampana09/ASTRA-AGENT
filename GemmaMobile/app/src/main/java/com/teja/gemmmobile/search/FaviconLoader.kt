package com.teja.gemmmobile.search

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.util.LruCache
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.net.HttpURLConnection
import java.net.URI
import java.net.URL

/**
 * High-performance on-device Favicon downloader and in-memory LRU cache.
 * Downloads real high-res site favicons (via Google Favicon CDN / DuckDuckGo / direct)
 * and caches them for instant circular favicon rendering in Search Sources & Profile Cards.
 */
object FaviconLoader {
    // 50 bitmap memory cache
    private val cache = LruCache<String, Bitmap>(50)

    fun getCached(url: String): Bitmap? {
        val domain = extractDomain(url)
        if (domain.isBlank()) return null
        return cache.get(domain)
    }

    suspend fun loadFavicon(url: String): Bitmap? = withContext(Dispatchers.IO) {
        val domain = extractDomain(url)
        if (domain.isBlank()) return@withContext null

        cache.get(domain)?.let { return@withContext it }

        // Primary: Google Favicon CDN (returns clean 128px PNGs with high reliability)
        val candidateUrls = listOf(
            "https://www.google.com/s2/favicons?domain=$domain&sz=128",
            "https://icons.duckduckgo.com/ip3/$domain.ico"
        )

        for (candidate in candidateUrls) {
            var conn: HttpURLConnection? = null
            try {
                conn = URL(candidate).openConnection() as HttpURLConnection
                conn.connectTimeout = 3000
                conn.readTimeout = 3000
                conn.instanceFollowRedirects = true
                conn.requestMethod = "GET"
                conn.setRequestProperty("User-Agent", "Mozilla/5.0")
                if (conn.responseCode == 200) {
                    val bytes = conn.inputStream.use { it.readBytes() }
                    if (bytes.isNotEmpty()) {
                        val bmp = BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
                        if (bmp != null) {
                            cache.put(domain, bmp)
                            return@withContext bmp
                        }
                    }
                }
            } catch (_: Exception) {
                // fallback to next candidate
            } finally {
                try { conn?.disconnect() } catch (_: Exception) {}
            }
        }
        null
    }

    fun extractDomain(url: String): String {
        return try {
            val host = URI(url).host ?: return ""
            host.removePrefix("www.").lowercase()
        } catch (_: Exception) {
            ""
        }
    }
}
