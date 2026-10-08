package com.teja.gemmmobile.tools

import android.content.Context
import android.net.Uri
import com.teja.gemmmobile.ocr.DocumentOcrHelper
import java.io.File

/**
 * On-device document text-extraction tool (PDF and plain-text files only).
 *
 * IMPORTANT: Images (jpg/png/webp/gif/bmp) MUST NOT be passed here.
 * Images go directly to the model as raw bytes for native vision analysis.
 * This tool only handles text-bearing documents.
 */
class OcrTool(
    private val context: Context
) : GemmaTool {

    override val name: String = "ocr_document"

    override val description: String =
        "Extracts text from a PDF or plain-text document file. " +
        "DO NOT use this for images (jpg, png, webp, etc.) — images are analyzed directly by the vision model without any text extraction."

    override val parametersJsonSchema: String = """
    {
      "type": "object",
      "properties": {
        "file_path": {
          "type": "string",
          "description": "The local file path or URI of a PDF or plain-text document to extract text from. Must NOT be an image file."
        }
      },
      "required": ["file_path"]
    }
    """.trimIndent()

    /** Image extensions that must never be passed to this tool. */
    private val IMAGE_EXTENSIONS = setOf("jpg", "jpeg", "png", "webp", "gif", "bmp", "heic", "heif")

    override suspend fun execute(arguments: Map<String, Any?>): ToolResult {
        val path = arguments["file_path"] as? String
            ?: return ToolResult.failure("Missing 'file_path'")

        val ext = path.substringAfterLast('.', "").lowercase()
        if (ext in IMAGE_EXTENSIONS) {
            return ToolResult.failure(
                "Images cannot be processed by ocr_document. " +
                "Send the image directly to the model for visual analysis instead."
            )
        }

        val file = File(path)
        if (!file.exists()) {
            return ToolResult.failure("File not found at: $path")
        }

        return try {
            val uri = Uri.fromFile(file)
            val doc = if (path.endsWith(".pdf", ignoreCase = true)) {
                DocumentOcrHelper.processPdfUri(context, uri)
            } else {
                DocumentOcrHelper.processTextUri(context, uri)
            }

            if (doc.text.isBlank()) {
                ToolResult.success("No readable text found in ${doc.fileName}.", data = doc)
            } else {
                ToolResult.success(
                    "Extracted text from ${doc.fileName} " +
                    "(${doc.pageCount} page(s), ${doc.wordCount} words):\n\n${doc.text.take(4000)}",
                    data = doc
                )
            }
        } catch (e: Exception) {
            ToolResult.failure("Text extraction failed: ${e.localizedMessage ?: "Unknown error"}")
        }
    }
}
