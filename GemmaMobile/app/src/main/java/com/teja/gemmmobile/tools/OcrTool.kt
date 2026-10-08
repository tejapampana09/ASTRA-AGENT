package com.teja.gemmmobile.tools

import android.content.Context
import android.net.Uri
import com.teja.gemmmobile.ocr.DocumentOcrHelper
import java.io.File

/**
 * On-device OCR tool utilizing DocumentOcrHelper and ML Kit.
 */
class OcrTool(
    private val context: Context
) : GemmaTool {

    override val name: String = "ocr_document"

    override val description: String =
        "Extracts text from an image, photo, or document file using on-device ML Kit OCR."

    override val parametersJsonSchema: String = """
    {
      "type": "object",
      "properties": {
        "file_path": {
          "type": "string",
          "description": "The local file path or URI of the document/image to perform OCR on."
        }
      },
      "required": ["file_path"]
    }
    """.trimIndent()

    override suspend fun execute(arguments: Map<String, Any?>): ToolResult {
        val path = arguments["file_path"] as? String ?: return ToolResult.failure("Missing 'file_path'")
        val file = File(path)
        if (!file.exists()) {
            return ToolResult.failure("File not found at: $path")
        }

        return try {
            val uri = Uri.fromFile(file)
            val doc = if (path.endsWith(".pdf", ignoreCase = true)) {
                DocumentOcrHelper.processPdfUri(context, uri)
            } else {
                DocumentOcrHelper.processImageUri(context, uri)
            }

            if (doc.text.isBlank()) {
                ToolResult.success("OCR completed but no readable text was detected.", data = doc)
            } else {
                ToolResult.success("Extracted Text from ${doc.fileName} (${doc.wordCount} words):\n\n${doc.text}", data = doc)
            }
        } catch (e: Exception) {
            ToolResult.failure("OCR failed: ${e.localizedMessage ?: "Unknown error"}")
        }
    }
}
