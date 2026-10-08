package com.teja.gemmmobile.ocr

import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.util.zip.Inflater
import java.util.zip.InflaterInputStream

/**
 * High-speed on-device digital PDF text extractor.
 * Parses PDF text streams (BT ... ET, Tj, TJ) directly in pure Kotlin without rendering bitmaps,
 * achieving <50ms extraction time for digital PDFs.
 */
object PdfTextExtractor {

    data class RawPdfPage(
        val pageNumber: Int,
        val text: String
    )

    /**
     * Extracts text from digital PDF bytes.
     * Returns a list of [DocumentPage] if digital text was successfully extracted.
     * Returns empty list if no meaningful digital text was found (e.g., scanned photocopy),
     * allowing the caller to fall back to ML Kit OCR.
     */
    fun extractText(pdfBytes: ByteArray, expectedPageCount: Int = 1): List<DocumentPage> {
        if (pdfBytes.isEmpty()) return emptyList()

        val streams = extractStreams(pdfBytes)
        if (streams.isEmpty()) return emptyList()

        val extractedPages = mutableListOf<DocumentPage>()
        val pageTexts = mutableListOf<String>()

        var currentStreamText = StringBuilder()
        for (stream in streams) {
            val text = parseContentStream(stream)
            if (text.isNotBlank()) {
                currentStreamText.append(text).append("\n")
            }
        }

        val allText = currentStreamText.toString().trim()
        val totalWords = if (allText.isBlank()) 0 else allText.split(Regex("""\s+""")).size

        // If less than 5 words across the entire document or very short, it's likely a scanned image PDF
        if (totalWords < 5 || allText.length < 15) {
            return emptyList()
        }

        // Try page-based splitting:
        // 1. Check if there are form feed characters (\u000c) or page break markers
        val rawPageSplits = allText.split("\u000c").map { it.trim() }.filter { it.isNotBlank() }
        if (rawPageSplits.size > 1 && rawPageSplits.size == expectedPageCount) {
            rawPageSplits.forEachIndexed { index, pageStr ->
                val headings = DocumentIntelligenceEngine.extractHeadings(pageStr)
                extractedPages.add(DocumentPage(pageNumber = index + 1, text = pageStr, headings = headings))
            }
            return extractedPages
        }

        // 2. If single continuous text and multiple expected pages, partition evenly by paragraphs
        if (expectedPageCount > 1) {
            val paragraphs = allText.split(Regex("""\n{2,}""")).map { it.trim() }.filter { it.isNotBlank() }
            if (paragraphs.isNotEmpty()) {
                val paragraphsPerPage = (paragraphs.size + expectedPageCount - 1) / expectedPageCount
                for (p in 0 until expectedPageCount) {
                    val start = p * paragraphsPerPage
                    val end = minOf(start + paragraphsPerPage, paragraphs.size)
                    if (start < paragraphs.size) {
                        val pageStr = paragraphs.subList(start, end).joinToString("\n\n")
                        val headings = DocumentIntelligenceEngine.extractHeadings(pageStr)
                        extractedPages.add(DocumentPage(pageNumber = p + 1, text = pageStr, headings = headings))
                    }
                }
            }
        }

        // 3. Fallback to single page if not split
        if (extractedPages.isEmpty()) {
            val headings = DocumentIntelligenceEngine.extractHeadings(allText)
            extractedPages.add(DocumentPage(pageNumber = 1, text = allText, headings = headings))
        }

        return extractedPages
    }

    /**
     * Extracts and decompresses all stream data from the PDF bytes.
     */
    internal fun extractStreams(bytes: ByteArray): List<String> {
        val streams = mutableListOf<String>()
        val streamMarker = "stream".toByteArray(Charsets.US_ASCII)
        val endStreamMarker = "endstream".toByteArray(Charsets.US_ASCII)

        var index = 0
        while (index < bytes.size) {
            val streamStart = indexOfBytes(bytes, streamMarker, index)
            if (streamStart == -1) break

            // Skip past "stream" and newline (\r\n or \n)
            var dataStart = streamStart + streamMarker.size
            if (dataStart < bytes.size && bytes[dataStart] == '\r'.code.toByte()) dataStart++
            if (dataStart < bytes.size && bytes[dataStart] == '\n'.code.toByte()) dataStart++

            val streamEnd = indexOfBytes(bytes, endStreamMarker, dataStart)
            if (streamEnd == -1) break

            // Examine header dictionary before "stream"
            val dictHeaderStart = maxOf(0, streamStart - 400)
            val headerText = String(bytes, dictHeaderStart, streamStart - dictHeaderStart, Charsets.ISO_8859_1)

            // Skip image XObjects
            val isImage = headerText.contains("/Subtype /Image") || headerText.contains("/Subtype/Image")
            if (!isImage && streamEnd > dataStart) {
                val streamBytes = bytes.copyOfRange(dataStart, streamEnd)
                val isFlate = headerText.contains("/FlateDecode")

                val decompressed = if (isFlate) {
                    decompressFlate(streamBytes)
                } else {
                    String(streamBytes, Charsets.ISO_8859_1)
                }

                if (!decompressed.isNullOrBlank() && decompressed.contains("BT")) {
                    streams.add(decompressed)
                }
            }

            index = streamEnd + endStreamMarker.size
        }

        return streams
    }

    private fun decompressFlate(bytes: ByteArray): String? {
        return try {
            val inflater = Inflater(false)
            val buffer = ByteArray(4096)
            val output = ByteArrayOutputStream()
            inflater.setInput(bytes)
            while (!inflater.finished()) {
                val count = inflater.inflate(buffer)
                if (count == 0) {
                    if (inflater.needsInput() || inflater.needsDictionary()) break
                }
                output.write(buffer, 0, count)
            }
            inflater.end()
            output.toString(Charsets.ISO_8859_1.name())
        } catch (_: Exception) {
            // Try InflaterInputStream fallback
            try {
                InflaterInputStream(ByteArrayInputStream(bytes)).use {
                    it.readBytes().toString(Charsets.ISO_8859_1)
                }
            } catch (_: Exception) {
                null
            }
        }
    }

    /**
     * Parses a decompressed PDF content stream and extracts visible text inside BT ... ET blocks.
     */
    internal fun parseContentStream(streamText: String): String {
        val result = StringBuilder()
        var pos = 0
        val len = streamText.length

        while (pos < len) {
            val btIndex = streamText.indexOf("BT", pos)
            if (btIndex == -1) break

            val etIndex = streamText.indexOf("ET", btIndex + 2)
            if (etIndex == -1) break

            val block = streamText.substring(btIndex + 2, etIndex)
            val blockText = extractTextFromBtBlock(block)
            if (blockText.isNotBlank()) {
                result.append(blockText).append("\n")
            }

            pos = etIndex + 2
        }

        return result.toString().trim()
    }

    internal fun extractTextFromBtBlock(block: String): String {
        val sb = StringBuilder()
        var i = 0
        val len = block.length

        while (i < len) {
            val char = block[i]
            if (char == '(') {
                // Literal string ( ... )
                val str = extractPdfString(block, i)
                i += str.first
                // Check following operator
                val following = block.substring(i, minOf(i + 15, len)).trimStart()
                if (following.startsWith("Tj") || following.startsWith("'") || following.startsWith("\"")) {
                    sb.append(str.second).append(" ")
                } else {
                    sb.append(str.second).append(" ")
                }
            } else if (char == '[') {
                // Array of strings [...] TJ
                val arrayContent = extractPdfArray(block, i)
                i += arrayContent.first
                val following = block.substring(i, minOf(i + 10, len)).trimStart()
                if (following.startsWith("TJ")) {
                    sb.append(arrayContent.second).append(" ")
                }
            } else if (char == 'T' && i + 1 < len && block[i + 1] == '*') {
                sb.append("\n")
                i += 2
            } else {
                i++
            }
        }

        return sb.toString().trim()
    }

    private fun extractPdfString(text: String, start: Int): Pair<Int, String> {
        val sb = StringBuilder()
        var depth = 1
        var i = start + 1
        val len = text.length

        while (i < len && depth > 0) {
            val c = text[i]
            if (c == '\\' && i + 1 < len) {
                val next = text[i + 1]
                when (next) {
                    'n' -> sb.append('\n')
                    'r' -> sb.append('\r')
                    't' -> sb.append('\t')
                    'b' -> sb.append('\b')
                    'f' -> sb.append('\u000c')
                    '(' -> sb.append('(')
                    ')' -> sb.append(')')
                    '\\' -> sb.append('\\')
                    in '0'..'7' -> {
                        // Octal sequence \ddd
                        var octal = "$next"
                        var k = i + 2
                        while (k < len && k < i + 4 && text[k] in '0'..'7') {
                            octal += text[k]
                            k++
                        }
                        try {
                            sb.append(octal.toInt(8).toChar())
                        } catch (_: Exception) {
                            sb.append(' ')
                        }
                        i = k
                        continue
                    }
                    else -> sb.append(next)
                }
                i += 2
            } else if (c == '(') {
                depth++
                sb.append(c)
                i++
            } else if (c == ')') {
                depth--
                if (depth > 0) sb.append(c)
                i++
            } else {
                sb.append(c)
                i++
            }
        }

        return Pair(i - start, sb.toString())
    }

    private fun extractPdfArray(text: String, start: Int): Pair<Int, String> {
        val sb = StringBuilder()
        var i = start + 1
        val len = text.length

        while (i < len && text[i] != ']') {
            val c = text[i]
            if (c == '(') {
                val str = extractPdfString(text, i)
                sb.append(str.second)
                i += str.first
            } else if (c == '-' && i + 3 < len) {
                // Negative kerning (space between words)
                val numStr = text.substring(i + 1).takeWhile { it.isDigit() }
                if (numStr.toIntOrNull()?.let { it > 100 } == true) {
                    sb.append(" ")
                }
                i += 1 + numStr.length
            } else {
                i++
            }
        }

        return Pair(if (i < len) i - start + 1 else len - start, sb.toString())
    }

    private fun indexOfBytes(source: ByteArray, target: ByteArray, fromIndex: Int = 0): Int {
        if (target.isEmpty() || fromIndex >= source.size) return -1
        val max = source.size - target.size
        for (i in fromIndex..max) {
            var found = true
            for (j in target.indices) {
                if (source[i + j] != target[j]) {
                    found = false
                    break
                }
            }
            if (found) return i
        }
        return -1
    }
}
