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

data class DocumentPage(
    val pageNumber: Int,
    val text: String,
    val headings: List<String> = emptyList()
)

data class ExtractedDocument(
    val fileName: String,
    val text: String,
    val wordCount: Int,
    val previewBitmap: Bitmap? = null,
    val isImage: Boolean = false,
    val imageUri: android.net.Uri? = null,
    val imageBytes: ByteArray? = null,
    val pageCount: Int = 1,
    val pages: List<DocumentPage> = emptyList()
)

object DocumentOcrHelper {

    private val recognizer by lazy {
        TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
    }

    suspend fun processImageUri(context: Context, uri: Uri): ExtractedDocument = withContext(Dispatchers.IO) {
        val fileName = getFileName(context, uri) ?: "Image.jpg"
        val rawBytes = try {
            context.contentResolver.openInputStream(uri)?.use { it.readBytes() }
        } catch (_: Exception) { null }

        // Automatically compress & scale for lightweight memory and disk footprint
        val bytes = rawBytes?.let { com.teja.gemmmobile.storage.StorageManagerHelper.compressForVision(it) } ?: rawBytes
        val bitmap = if (bytes != null) {
            try { android.graphics.BitmapFactory.decodeByteArray(bytes, 0, bytes.size) } catch (_: Exception) { null }
        } else null

        val image = InputImage.fromFilePath(context, uri)
        val visionText = recognizer.process(image).await()
        val text = visionText.text.trim()
        val words = if (text.isBlank()) 0 else text.split(Regex("""\s+""")).size
        ExtractedDocument(
            fileName = fileName,
            text = text,
            wordCount = words,
            previewBitmap = bitmap,
            isImage = true,
            imageUri = uri,
            imageBytes = bytes
        )
    }

    suspend fun processImageBitmap(bitmap: Bitmap, name: String = "Photo"): ExtractedDocument = withContext(Dispatchers.IO) {
        val scaled = com.teja.gemmmobile.storage.StorageManagerHelper.scaleBitmapDown(bitmap, 1024)
        val image = InputImage.fromBitmap(scaled, 0)
        val visionText = recognizer.process(image).await()
        val text = visionText.text.trim()
        val words = if (text.isBlank()) 0 else text.split(Regex("""\s+""")).size

        val stream = java.io.ByteArrayOutputStream()
        scaled.compress(Bitmap.CompressFormat.JPEG, 80, stream)
        val bytes = stream.toByteArray()

        ExtractedDocument(
            fileName = name,
            text = text,
            wordCount = words,
            previewBitmap = scaled,
            isImage = true,
            imageBytes = bytes
        )
    }

    suspend fun processPdfUri(context: Context, uri: Uri, maxPages: Int = 30): ExtractedDocument = withContext(Dispatchers.IO) {
        val fileName = getFileName(context, uri) ?: "Document.pdf"
        val sb = StringBuilder()
        var firstPageBitmap: Bitmap? = null
        val pagesList = mutableListOf<DocumentPage>()

        val pfd = context.contentResolver.openFileDescriptor(uri, "r")
        if (pfd != null) {
            pfd.use { descriptor ->
                PdfRenderer(descriptor).use { renderer ->
                    val totalPages = minOf(renderer.pageCount, maxPages)
                    for (i in 0 until totalPages) {
                        renderer.openPage(i).use { page ->
                            val scale = 2
                            val width = page.width * scale
                            val height = page.height * scale
                            val bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
                            
                            val canvas = android.graphics.Canvas(bitmap)
                            canvas.drawColor(android.graphics.Color.WHITE)

                            page.render(bitmap, null, null, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY)

                            if (i == 0) {
                                firstPageBitmap = com.teja.gemmmobile.storage.StorageManagerHelper.scaleBitmapDown(bitmap, 512)
                            }

                            val inputImage = InputImage.fromBitmap(bitmap, 0)
                            val visionText = recognizer.process(inputImage).await()
                            val pageContent = visionText.text.trim()

                            // Immediately recycle intermediate bitmap to conserve device RAM
                            if (i > 0) {
                                try { bitmap.recycle() } catch (_: Throwable) {}
                            }

                            if (pageContent.isNotBlank()) {
                                if (renderer.pageCount > 1) {
                                    sb.append("--- Page ${i + 1} ---\n")
                                }
                                sb.append(pageContent).append("\n\n")

                                val headings = DocumentIntelligenceEngine.extractHeadings(pageContent)
                                pagesList.add(DocumentPage(pageNumber = i + 1, text = pageContent, headings = headings))
                            }
                        }
                    }
                }
            }
        }

        val text = sb.toString().trim()
        val words = if (text.isBlank()) 0 else text.split(Regex("""\s+""")).size
        ExtractedDocument(
            fileName = fileName,
            text = text,
            wordCount = words,
            previewBitmap = firstPageBitmap,
            pageCount = if (pagesList.isNotEmpty()) pagesList.size else 1,
            pages = pagesList
        )
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
