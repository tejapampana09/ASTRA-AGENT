package com.teja.gemmmobile.ocr

/**
 * Splits extracted document pages into fixed-size word chunks for RAG-style retrieval.
 *
 * Each chunk is ~300 words (~400 tokens), small enough to fit inside the 2048-token budget
 * alongside a prompt and model response.
 *
 * Chunking is page-aware: a chunk never spans more than one page, so page citations remain
 * accurate even after retrieval.
 */
data class DocumentChunk(
    val text: String,
    val pageNumber: Int,
    val chunkIndex: Int,
    val wordCount: Int
)

object DocumentChunker {

    /** Words per chunk — keeps one chunk ≈ 400 tokens, leaving room for prompt + response. */
    private const val CHUNK_WORDS = 300

    /**
     * Splits a list of [DocumentPage]s into [DocumentChunk]s.
     *
     * Each page is word-tokenised and split into non-overlapping windows of [CHUNK_WORDS] words.
     * Pages with no usable text are skipped silently.
     */
    fun chunk(pages: List<DocumentPage>): List<DocumentChunk> {
        val chunks = mutableListOf<DocumentChunk>()
        var chunkIndex = 0

        for (page in pages) {
            val words = page.text
                .split(Regex("""\s+"""))
                .filter { it.isNotBlank() }

            if (words.isEmpty()) continue

            var i = 0
            while (i < words.size) {
                val end = minOf(i + CHUNK_WORDS, words.size)
                val chunkWords = words.subList(i, end)
                chunks.add(
                    DocumentChunk(
                        text = chunkWords.joinToString(" "),
                        pageNumber = page.pageNumber,
                        chunkIndex = chunkIndex++,
                        wordCount = chunkWords.size
                    )
                )
                i += CHUNK_WORDS
            }
        }

        return chunks
    }

    /**
     * Returns the chunks that correspond to the first [pageCount] pages.
     * Useful for summary / takeaway intents that care about the document opening.
     */
    fun chunksForFirstPages(chunks: List<DocumentChunk>, pageCount: Int): List<DocumentChunk> =
        chunks.filter { it.pageNumber <= pageCount }

    /**
     * Returns chunks for the last [pageCount] pages in the document.
     */
    fun chunksForLastPages(chunks: List<DocumentChunk>, pageCount: Int): List<DocumentChunk> {
        val maxPage = chunks.maxOfOrNull { it.pageNumber } ?: return emptyList()
        val threshold = maxPage - pageCount + 1
        return chunks.filter { it.pageNumber >= threshold }
    }

    /**
     * Builds a compact context string from a list of chunks, grouped by page number,
     * truncated to [maxChars] total characters.
     */
    fun buildContext(chunks: List<DocumentChunk>, maxChars: Int = 3000): String {
        val sb = StringBuilder()
        var remaining = maxChars
        var lastPage = -1

        for (chunk in chunks) {
            if (remaining <= 0) break
            if (chunk.pageNumber != lastPage) {
                val header = "\n--- Page ${chunk.pageNumber} ---\n"
                if (remaining < header.length) break
                sb.append(header)
                remaining -= header.length
                lastPage = chunk.pageNumber
            }
            val text = chunk.text.take(remaining)
            sb.append(text)
            remaining -= text.length
        }

        return sb.toString().trim()
    }
}
