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
    val pages: List<DocumentPage> = emptyList(),
    /** Pre-built word chunks for token-safe RAG retrieval (covers ALL pages). */
    val chunks: List<DocumentChunk> = emptyList()
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

        ExtractedDocument(
            fileName = fileName,
            text = "",
            wordCount = 0,
            previewBitmap = bitmap,
            isImage = true,
            imageUri = uri,
            imageBytes = bytes
        )
    }

    suspend fun processImageBitmap(bitmap: Bitmap, name: String = "Photo"): ExtractedDocument = withContext(Dispatchers.IO) {
        val scaled = com.teja.gemmmobile.storage.StorageManagerHelper.scaleBitmapDown(bitmap, 1024)
        val stream = java.io.ByteArrayOutputStream()
        scaled.compress(Bitmap.CompressFormat.JPEG, 80, stream)
        val bytes = stream.toByteArray()

        ExtractedDocument(
            fileName = name,
            text = "",
            wordCount = 0,
            previewBitmap = scaled,
            isImage = true,
            imageBytes = bytes
        )
    }

    suspend fun processPdfUri(context: Context, uri: Uri, maxPages: Int = 30): ExtractedDocument = withContext(Dispatchers.IO) {
        val fileName = getFileName(context, uri) ?: "Document.pdf"
        var firstPageBitmap: Bitmap? = null
        var totalPageCount = 1

        // 1. Read raw bytes and render page 0 thumbnail
        val rawBytes = try {
            context.contentResolver.openInputStream(uri)?.use { it.readBytes() }
        } catch (_: Exception) { null }

        val pfd = try {
            context.contentResolver.openFileDescriptor(uri, "r")
        } catch (_: Exception) { null }

        if (pfd != null) {
            pfd.use { descriptor ->
                try {
                    PdfRenderer(descriptor).use { renderer ->
                        totalPageCount = renderer.pageCount
                        if (renderer.pageCount > 0) {
                            renderer.openPage(0).use { page ->
                                val bitmap = Bitmap.createBitmap(page.width, page.height, Bitmap.Config.ARGB_8888)
                                val canvas = android.graphics.Canvas(bitmap)
                                canvas.drawColor(android.graphics.Color.WHITE)
                                page.render(bitmap, null, null, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY)
                                firstPageBitmap = com.teja.gemmmobile.storage.StorageManagerHelper.scaleBitmapDown(bitmap, 512)
                            }
                        }
                    }
                } catch (_: Exception) {}
            }
        }

        // 2. High-speed digital text extraction (<50ms, Google AI Edge Gallery standard)
        val digitalPages = if (rawBytes != null) {
            PdfTextExtractor.extractText(rawBytes, expectedPageCount = minOf(totalPageCount, maxPages))
        } else emptyList()

        if (digitalPages.isNotEmpty()) {
            val sb = StringBuilder()
            digitalPages.forEachIndexed { _, page ->
                if (digitalPages.size > 1) {
                    sb.append("--- Page ${page.pageNumber} ---\n")
                }
                sb.append(page.text).append("\n\n")
            }
            val text = sb.toString().trim()
            val words = if (text.isBlank()) 0 else text.split(Regex("""\s+""")).size
            val chunks = DocumentChunker.chunk(digitalPages)
            return@withContext ExtractedDocument(
                fileName = fileName,
                text = text,
                wordCount = words,
                previewBitmap = firstPageBitmap,
                pageCount = digitalPages.size,
                pages = digitalPages,
                chunks = chunks
            )
        }

        // 3. Fallback: On-device ML Kit OCR only when digital text is absent (e.g. scanned books/invoices)
        val sb = StringBuilder()
        val pagesList = mutableListOf<DocumentPage>()
        val fallbackPfd = try {
            context.contentResolver.openFileDescriptor(uri, "r")
        } catch (_: Exception) { null }

        if (fallbackPfd != null) {
            fallbackPfd.use { descriptor ->
                PdfRenderer(descriptor).use { renderer ->
                    val pagesToOcr = minOf(renderer.pageCount, maxPages)
                    for (i in 0 until pagesToOcr) {
                        renderer.openPage(i).use { page ->
                            val scale = 2
                            val width = page.width * scale
                            val height = page.height * scale
                            val bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
                            val canvas = android.graphics.Canvas(bitmap)
                            canvas.drawColor(android.graphics.Color.WHITE)
                            page.render(bitmap, null, null, PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY)

                            val inputImage = InputImage.fromBitmap(bitmap, 0)
                            val visionText = recognizer.process(inputImage).await()
                            val pageContent = visionText.text.trim()

                            try { bitmap.recycle() } catch (_: Throwable) {}

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
        val chunks = DocumentChunker.chunk(pagesList)
        ExtractedDocument(
            fileName = fileName,
            text = text,
            wordCount = words,
            previewBitmap = firstPageBitmap,
            pageCount = if (pagesList.isNotEmpty()) pagesList.size else 1,
            pages = pagesList,
            chunks = chunks
        )
    }

    suspend fun processTextUri(context: Context, uri: Uri): ExtractedDocument = withContext(Dispatchers.IO) {
        val fileName = getFileName(context, uri) ?: "document.txt"
        val text = context.contentResolver.openInputStream(uri)?.bufferedReader()?.use { it.readText() } ?: ""
        val trimmed = text.trim()
        val words = if (trimmed.isBlank()) 0 else trimmed.split(Regex("""\s+""")).size
        val headings = DocumentIntelligenceEngine.extractHeadings(trimmed)
        val pages = if (trimmed.isNotBlank()) {
            listOf(DocumentPage(pageNumber = 1, text = trimmed, headings = headings))
        } else emptyList()
        ExtractedDocument(
            fileName = fileName,
            text = trimmed,
            wordCount = words,
            pageCount = 1,
            pages = pages
        )
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
