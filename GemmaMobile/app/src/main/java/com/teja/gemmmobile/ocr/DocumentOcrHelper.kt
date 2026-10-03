package com.teja.gemmmobile.ocr

import android.content.Context
import android.graphics.Bitmap
import android.graphics.pdf.PdfRenderer
import android.net.Uri
import android.provider.OpenableColumns
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.tasks.await
import kotlinx.coroutines.withContext

data class ExtractedDocument(
    val fileName: String,
    val text: String,
    val wordCount: Int,
    val previewBitmap: Bitmap? = null,
    val isImage: Boolean = false,
    val imageUri: android.net.Uri? = null,
    val imageBytes: ByteArray? = null
)

object DocumentOcrHelper {

    private val recognizer by lazy {
        TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
    }

    suspend fun processImageUri(context: Context, uri: Uri): ExtractedDocument = withContext(Dispatchers.IO) {
        val fileName = getFileName(context, uri) ?: "Image.jpg"
        val image = InputImage.fromFilePath(context, uri)
        val visionText = recognizer.process(image).await()
        val text = visionText.text.trim()
        val words = if (text.isBlank()) 0 else text.split(Regex("""\s+""")).size
        ExtractedDocument(fileName, text, words)
    }

    suspend fun processImageBitmap(bitmap: Bitmap, name: String = "Photo"): ExtractedDocument = withContext(Dispatchers.IO) {
        val image = InputImage.fromBitmap(bitmap, 0)
        val visionText = recognizer.process(image).await()
        val text = visionText.text.trim()
        val words = if (text.isBlank()) 0 else text.split(Regex("""\s+""")).size
        ExtractedDocument(name, text, words, previewBitmap = bitmap)
    }

    suspend fun processPdfUri(context: Context, uri: Uri, maxPages: Int = 10): ExtractedDocument = withContext(Dispatchers.IO) {
        val fileName = getFileName(context, uri) ?: "Document.pdf"
        val sb = StringBuilder()
        var firstPageBitmap: Bitmap? = null

        val pfd = context.contentResolver.openFileDescriptor(uri, "r")
        if (pfd != null) {
            pfd.use { descriptor ->
                PdfRenderer(descriptor).use { renderer ->
                    val totalPages = minOf(renderer.pageCount, maxPages)
                    for (i in 0 until totalPages) {
                        renderer.openPage(i).use { page ->
                            // Scale 2x for crisp OCR readability
                            val scale = 2
                            val width = page.width * scale
                            val height = page.height * scale
                            val bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
                            
                            // Fill background with white before rendering
                            val canvas = android.graphics.Canvas(bitmap)
                            canvas.drawColor(android.graphics.Color.WHITE)

                            page.render(bitmap, null, null, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY)

                            if (i == 0) {
                                firstPageBitmap = bitmap
                            }

                            val inputImage = InputImage.fromBitmap(bitmap, 0)
                            val visionText = recognizer.process(inputImage).await()
                            val pageContent = visionText.text.trim()

                            if (pageContent.isNotBlank()) {
                                if (renderer.pageCount > 1) {
                                    sb.append("--- Page ${i + 1} ---\n")
                                }
                                sb.append(pageContent).append("\n\n")
                            }
                        }
                    }
                }
            }
        }

        val text = sb.toString().trim()
        val words = if (text.isBlank()) 0 else text.split(Regex("""\s+""")).size
        ExtractedDocument(fileName, text, words, previewBitmap = firstPageBitmap)
    }

    suspend fun processTextUri(context: Context, uri: Uri): ExtractedDocument = withContext(Dispatchers.IO) {
        val fileName = getFileName(context, uri) ?: "document.txt"
        val text = context.contentResolver.openInputStream(uri)?.bufferedReader()?.use { it.readText() } ?: ""
        val trimmed = text.trim()
        val words = if (trimmed.isBlank()) 0 else trimmed.split(Regex("""\s+""")).size
        ExtractedDocument(fileName, trimmed, words)
    }

    fun getFileName(context: Context, uri: Uri): String? {
        var name: String? = null
        if (uri.scheme == "content") {
            context.contentResolver.query(uri, null, null, null, null)?.use { cursor ->
                val nameIndex = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                if (nameIndex != -1 && cursor.moveToFirst()) {
                    name = cursor.getString(nameIndex)
                }
            }
        }
        if (name == null) {
            name = uri.path?.let { p ->
                val cut = p.lastIndexOf('/')
                if (cut != -1) p.substring(cut + 1) else p
            }
        }
        return name
    }
}
