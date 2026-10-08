package com.teja.gemmmobile.storage

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.util.Log
import com.teja.gemmmobile.ui.ChatMessage
import com.teja.gemmmobile.ui.ChatSession
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.FileOutputStream

/**
 * Storage & Cache Management Helper.
 * Ensures uploaded images/documents do not bloat phone internal storage:
 * - Automatically downscales and compresses uploaded images to ~1024px JPEG (reducing 10MB to <100KB, >98% space saving).
 * - Automatically cleans up image files when a chat session is deleted.
 * - Scans and removes orphaned image files not tied to any active chat.
 * - Provides storage usage metrics and cache clearing functionality.
 */
object StorageManagerHelper {
    private const val TAG = "StorageManagerHelper"
    const val MAX_IMAGE_DIMENSION = 1024
    const val JPEG_QUALITY = 80

    /**
     * Compresses the image and writes it to internal app storage under `chat_images`.
     * Scales image so max dimension is <= 1024px and saves as ~80% quality JPEG.
     */
    suspend fun compressAndSaveImage(
        context: Context,
        previewBitmap: Bitmap?,
        rawBytes: ByteArray?,
        messageId: String
    ): String? = withContext(Dispatchers.IO) {
        compressAndSaveImageSync(context, previewBitmap, rawBytes, messageId)
    }

    /**
     * Synchronous version of compressAndSaveImage for direct non-suspend calls.
     */
    fun compressAndSaveImageSync(
        context: Context,
        previewBitmap: Bitmap?,
        rawBytes: ByteArray?,
        messageId: String
    ): String? {
        return try {
            val dir = File(context.filesDir, "chat_images").apply { mkdirs() }
            val targetFile = File(dir, "${messageId}.jpg")

            val sourceBitmap = previewBitmap ?: rawBytes?.let { bytes ->
                try {
                    BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
                } catch (e: Exception) {
                    null
                }
            } ?: return null

            val scaledBitmap = scaleBitmapDown(sourceBitmap, MAX_IMAGE_DIMENSION)
            FileOutputStream(targetFile).use { outStream ->
                scaledBitmap.compress(Bitmap.CompressFormat.JPEG, JPEG_QUALITY, outStream)
            }

            if (scaledBitmap != sourceBitmap && scaledBitmap != previewBitmap) {
                try { scaledBitmap.recycle() } catch (_: Throwable) {}
            }

            Log.d(TAG, "[$TAG] Compressed image saved to ${targetFile.absolutePath} (${targetFile.length() / 1024} KB)")
            targetFile.absolutePath
        } catch (e: Exception) {
            Log.e(TAG, "[$TAG] Error compressing & saving image", e)
            null
        }
    }

    /**
     * Downscales image bytes into standard-dimension JPEG bytes for optimal LiteRT vision encoding.
     */
    fun compressForVision(rawBytes: ByteArray?, maxDimension: Int = MAX_IMAGE_DIMENSION): ByteArray? {
        if (rawBytes == null || rawBytes.isEmpty()) return null
        return try {
            val bitmap = BitmapFactory.decodeByteArray(rawBytes, 0, rawBytes.size) ?: return rawBytes
            val scaled = scaleBitmapDown(bitmap, maxDimension)
            val stream = ByteArrayOutputStream()
            scaled.compress(Bitmap.CompressFormat.JPEG, JPEG_QUALITY, stream)
            if (scaled != bitmap) {
                try { scaled.recycle() } catch (_: Throwable) {}
            }
            try { bitmap.recycle() } catch (_: Throwable) {}
            stream.toByteArray()
        } catch (e: Exception) {
            Log.w(TAG, "[$TAG] Failed to compress image for vision, using raw bytes", e)
            rawBytes
        }
    }

    /**
     * Downscales a bitmap to fit within maxDimension while maintaining aspect ratio.
     */
    fun scaleBitmapDown(bitmap: Bitmap, maxDimension: Int): Bitmap {
        val width = bitmap.width
        val height = bitmap.height
        if (width <= maxDimension && height <= maxDimension) {
            return bitmap
        }
        val ratio = width.toFloat() / height.toFloat()
        val targetWidth: Int
        val targetHeight: Int
        if (ratio > 1f) {
            targetWidth = maxDimension
            targetHeight = (maxDimension / ratio).toInt().coerceAtLeast(1)
        } else {
            targetHeight = maxDimension
            targetWidth = (maxDimension * ratio).toInt().coerceAtLeast(1)
        }
        return Bitmap.createScaledBitmap(bitmap, targetWidth, targetHeight, true)
    }

    /**
     * Deletes physical image files for a specific list of messages (e.g. when a chat session is deleted).
     */
    suspend fun deleteSessionImages(messages: List<ChatMessage>) = withContext(Dispatchers.IO) {
        messages.forEach { msg ->
            msg.imagePath?.let { path ->
                try {
                    val file = File(path)
                    if (file.exists()) {
                        val deleted = file.delete()
                        Log.d(TAG, "[$TAG] Deleted session image: $path ($deleted)")
                    }
                } catch (e: Exception) {
                    Log.w(TAG, "[$TAG] Failed to delete image file: $path", e)
                }
            }
        }
    }

    /**
     * Deletes all saved chat images on device (e.g. when clearing all chats).
     */
    suspend fun deleteAllImages(context: Context) = withContext(Dispatchers.IO) {
        try {
            val dir = File(context.filesDir, "chat_images")
            if (dir.exists()) {
                dir.listFiles()?.forEach { it.delete() }
            }
        } catch (e: Exception) {
            Log.w(TAG, "[$TAG] Failed to delete all chat images", e)
        }
    }

    /**
     * Scans `chat_images` directory and removes any files not referenced by any active chat session.
     */
    suspend fun cleanOrphanImages(context: Context, activeSessions: List<ChatSession>): Int = withContext(Dispatchers.IO) {
        try {
            val dir = File(context.filesDir, "chat_images")
            if (!dir.exists()) return@withContext 0

            val referencedPaths = activeSessions
                .flatMap { it.messages }
                .mapNotNull { it.imagePath }
                .toSet()

            var deletedCount = 0
            dir.listFiles()?.forEach { file ->
                if (!referencedPaths.contains(file.absolutePath)) {
                    if (file.delete()) {
                        deletedCount++
                        Log.d(TAG, "[$TAG] Cleaned orphan image: ${file.name}")
                    }
                }
            }
            deletedCount
        } catch (e: Exception) {
            Log.e(TAG, "[$TAG] Error cleaning orphan images", e)
            0
        }
    }

    /**
     * Returns total storage size in bytes of attached chat images.
     */
    fun getChatImagesSizeBytes(context: Context): Long {
        val dir = File(context.filesDir, "chat_images")
        return getFolderSize(dir)
    }

    /**
     * Returns total temporary cache size in bytes.
     */
    fun getCacheSizeBytes(context: Context): Long {
        return getFolderSize(context.cacheDir)
    }

    /**
     * Clears temporary cache directory and trims orphan files.
     */
    suspend fun clearCache(context: Context, activeSessions: List<ChatSession>): Long = withContext(Dispatchers.IO) {
        val before = getCacheSizeBytes(context) + getChatImagesSizeBytes(context)
        try {
            // Delete files in cacheDir
            context.cacheDir.listFiles()?.forEach { it.deleteRecursively() }
            // Clean orphan images
            cleanOrphanImages(context, activeSessions)
        } catch (e: Exception) {
            Log.w(TAG, "[$TAG] Error clearing cache", e)
        }
        val after = getCacheSizeBytes(context) + getChatImagesSizeBytes(context)
        (before - after).coerceAtLeast(0L)
    }

    private fun getFolderSize(dir: File?): Long {
        if (dir == null || !dir.exists()) return 0L
        var size = 0L
        dir.listFiles()?.forEach { file ->
            size += if (file.isDirectory) getFolderSize(file) else file.length()
        }
        return size
    }

    fun formatBytes(bytes: Long): String {
        return when {
            bytes >= 1024L * 1024L * 1024L -> String.format(java.util.Locale.US, "%.2f GB", bytes.toDouble() / (1024.0 * 1024.0 * 1024.0))
            bytes >= 1024L * 1024L -> String.format(java.util.Locale.US, "%.1f MB", bytes.toDouble() / (1024.0 * 1024.0))
            bytes >= 1024L -> String.format(java.util.Locale.US, "%.0f KB", bytes.toDouble() / 1024.0)
            else -> "$bytes B"
        }
    }
}
