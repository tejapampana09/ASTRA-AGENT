package com.teja.gemmmobile.ocr

import android.util.Log

data class DocumentPromptResult(
    val promptForModel: String,
    val citedPages: List<Int> = emptyList(),
    val intent: DocumentIntent
)

enum class DocumentIntent {
    TOPIC_EXTRACTION,
    FULL_SUMMARY,
    KEY_TAKEAWAYS,
    SPECIFIC_QA
}

/**
 * On-device Document Intelligence Engine for Gemma 4 E2B.
 *
 * DESIGN PRINCIPLE for small on-device models:
 * - Simple, direct prompts — no complex ### headers or CRITICAL RULE markers
 * - Content FIRST, then instruction — model reads content before being told what to do
 * - Short, clear questions — small models follow simple instructions better
 * - Token budget: ~1 200 chars of document content (≈ 400 tokens), leaving
 *   ~1 600 tokens for prompt overhead and response within the 2 048-token ceiling.
 */
object DocumentIntelligenceEngine {

    private const val TAG = "DocIntelligence"

    // Noise words that are watermarks/logos/page-numbers, not real headings
    private val HEADING_NOISE = setOf(
        "university", "college", "institute", "department", "school",
        "copyright", "confidential", "proprietary", "all rights reserved",
        "thank you", "questions", "references", "bibliography", "appendix",
        "osrm", "srm", "ap", "india", "andhra pradesh"
    )

    // -----------------------------------------------------------------------
    // Heading extractor (called during ingestion to annotate pages)
    // -----------------------------------------------------------------------

    fun extractHeadings(pageText: String): List<String> {
        if (pageText.isBlank()) return emptyList()
        val lines = pageText.lines().map { it.trim() }.filter { it.isNotBlank() }
        val headings = mutableListOf<String>()

        val headingRegex = Regex(
            """^(?:Chapter|Section|Module|Part|Unit|\d+(?:\.\d+)*)\s+.+""",
            RegexOption.IGNORE_CASE
        )
        // All-caps short title (e.g., "INTRODUCTION TO PFAS") — min 10 chars to avoid logo junk
        val allCapsRegex = Regex("""^[A-Z][A-Z0-9\s:–—\-]{9,59}$""")

        for (line in lines) {
            val lower = line.lowercase().trim()
            // Skip noise words (logos, watermarks, page numbers)
            if (HEADING_NOISE.any { lower == it || lower.startsWith(it + " ") || lower.endsWith(" " + it) }) continue
            if (lower.all { it.isDigit() || it.isWhitespace() }) continue // pure numbers = page #

            when {
                headingRegex.matches(line) && line.length >= 8 ->
                    headings.add(line.take(80))
                allCapsRegex.matches(line) && !line.endsWith(".") ->
                    headings.add(line.take(80))
                line.startsWith("#") ->
                    headings.add(line.removePrefix("#").trim().take(80))
            }
        }
        return headings.distinct()
            .filter { it.split(" ").size >= 2 } // must be at least 2 words
            .take(8)
    }

    // -----------------------------------------------------------------------
    // Intent detection
    // -----------------------------------------------------------------------

    fun detectIntent(query: String): DocumentIntent {
        val q = query.lowercase().trim()

        val topicKeywords = listOf(
            "topic", "topics", "index", "table of content", "toc", "syllabus",
            "chapters", "chapter", "outline", "list topics", "contents", "headings",
            "sections", "subtopics", "what are the topics", "show index", "all topics"
        )
        if (topicKeywords.any { q.contains(it) }) return DocumentIntent.TOPIC_EXTRACTION

        val takeawaysKeywords = listOf(
            "takeaway", "takeaways", "key takeaways", "key findings", "highlights",
            "action items", "conclusions", "core insights", "key takeaway"
        )
        if (takeawaysKeywords.any { q.contains(it) }) return DocumentIntent.KEY_TAKEAWAYS

        val summaryKeywords = listOf(
            "summarize", "summary", "overview", "explain full", "explain all",
            "what is this", "what is this pdf", "about", "explain document",
            "explain this pdf", "main points", "tl;dr", "tldr"
        )
        if (q.isBlank() || summaryKeywords.any { q.contains(it) }) return DocumentIntent.FULL_SUMMARY

        return DocumentIntent.SPECIFIC_QA
    }

    // -----------------------------------------------------------------------
    // Legacy page-level search (kept for backwards compatibility)
    // -----------------------------------------------------------------------

    fun searchRelevantPages(
        pages: List<DocumentPage>,
        query: String,
        maxResults: Int = 3
    ): List<DocumentPage> {
        if (pages.isEmpty()) return emptyList()
        if (pages.size <= maxResults) return pages

        val stopWords = setOf(
            "what", "is", "the", "in", "of", "and", "to", "a", "an", "this", "that",
            "for", "on", "with", "as", "by", "at", "from", "pdf", "document", "tell",
            "me", "about", "how", "why", "does", "can", "explain", "please"
        )
        val queryKeywords = query.lowercase()
            .split(Regex("""[^a-zA-Z0-9_]+"""))
            .filter { it.length > 2 && it !in stopWords }

        if (queryKeywords.isEmpty()) return pages.take(maxResults)

        val scored = pages.map { page ->
            val pageLower = page.text.lowercase()
            var score = 0
            for (kw in queryKeywords) {
                score += (pageLower.split(kw).size - 1) * 2
                if (page.headings.any { it.lowercase().contains(kw) }) score += 5
            }
            Pair(page, score)
        }
        val sorted = scored.filter { it.second > 0 }.sortedByDescending { it.second }.map { it.first }
        return if (sorted.isNotEmpty()) sorted.take(maxResults) else pages.take(maxResults)
    }

    // -----------------------------------------------------------------------
    // Main prompt builder — simple, direct prompts for small on-device model
    // -----------------------------------------------------------------------

    fun buildDocumentPrompt(doc: ExtractedDocument, rawUserQuery: String): DocumentPromptResult {
        val intent = detectIntent(rawUserQuery)
        val pages = doc.pages.ifEmpty {
            listOf(DocumentPage(pageNumber = 1, text = doc.text))
        }
        val chunks = doc.chunks.ifEmpty { DocumentChunker.chunk(pages) }

        Log.d(TAG, "intent=$intent pages=${pages.size} chunks=${chunks.size} query='$rawUserQuery'")

        return when (intent) {

            // ------------------------------------------------------------------
            // TOPIC EXTRACTION — TF-IDF over all chunks, no token limit
            // ------------------------------------------------------------------
            DocumentIntent.TOPIC_EXTRACTION -> {
                val topics = TfIdfExtractor.extractTopics(chunks, topN = 20)
                val topicsText = TfIdfExtractor.formatTopicsForPrompt(topics)
                val cleanHeadings = pages
                    .flatMap { p -> p.headings.map { "Page ${p.pageNumber}: $it" } }
                    .distinct().take(15)

                // Simple prompt: content first, then a plain question
                val prompt = buildString {
                    appendLine("The following are the main topics found in \"${doc.fileName}\" (${doc.pageCount} pages):")
                    appendLine()
                    appendLine(topicsText)
                    if (cleanHeadings.isNotEmpty()) {
                        appendLine()
                        appendLine("Section headings detected:")
                        cleanHeadings.forEach { appendLine("  $it") }
                    }
                    appendLine()
                    val question = if (rawUserQuery.isNotBlank()) rawUserQuery
                                   else "List all the topics and chapters in this document."
                    appendLine("User question: $question")
                    appendLine()
                    appendLine("Present a clean, numbered topic index based on the above. Group related topics, add page references, and ask which topic the user wants to explore.")
                }.trim()

                val citedPages = topics.flatMap { it.pageNumbers }.distinct().sorted().take(10)
                DocumentPromptResult(prompt, citedPages, intent)
            }

            // ------------------------------------------------------------------
            // FULL SUMMARY — intro + conclusion, simple instruction
            // ------------------------------------------------------------------
            DocumentIntent.FULL_SUMMARY -> {
                val firstChunks = DocumentChunker.chunksForFirstPages(chunks, pageCount = 3).take(4)
                val lastChunks = if (pages.size > 3)
                    DocumentChunker.chunksForLastPages(chunks, pageCount = 2).take(2)
                else emptyList()

                val intro = DocumentChunker.buildContext(firstChunks, maxChars = 1_800)
                val conclusion = DocumentChunker.buildContext(lastChunks, maxChars = 900)
                val cleanHeadings = pages
                    .flatMap { p -> p.headings.map { it } }
                    .distinct().take(10)

                // Simple, direct prompt — no complex headers
                val prompt = buildString {
                    appendLine("Read the following excerpts from \"${doc.fileName}\" (${doc.pageCount} pages) and write a summary.")
                    appendLine()
                    appendLine("--- Beginning of document ---")
                    appendLine(intro)
                    if (cleanHeadings.isNotEmpty()) {
                        appendLine()
                        appendLine("Key sections covered: ${cleanHeadings.joinToString(" | ")}")
                    }
                    if (conclusion.isNotBlank()) {
                        appendLine()
                        appendLine("--- End of document ---")
                        appendLine(conclusion)
                    }
                    appendLine()
                    appendLine("Write a clear executive summary covering: (1) what this document is about, (2) the main topics and key findings, (3) the most important takeaway. Cite page numbers where relevant.")
                }.trim()

                val citedPages = (firstChunks + lastChunks).map { it.pageNumber }.distinct().sorted()
                DocumentPromptResult(prompt, citedPages, intent)
            }

            // ------------------------------------------------------------------
            // KEY TAKEAWAYS — intro + conclusion, simple bullet instruction
            // ------------------------------------------------------------------
            DocumentIntent.KEY_TAKEAWAYS -> {
                val firstChunks = DocumentChunker.chunksForFirstPages(chunks, pageCount = 2).take(3)
                val lastChunks = if (pages.size > 2)
                    DocumentChunker.chunksForLastPages(chunks, pageCount = 2).take(2)
                else emptyList()

                val intro = DocumentChunker.buildContext(firstChunks, maxChars = 1_400)
                val conclusion = DocumentChunker.buildContext(lastChunks, maxChars = 900)

                val prompt = buildString {
                    appendLine("Read the following excerpts from \"${doc.fileName}\" (${doc.pageCount} pages).")
                    appendLine()
                    appendLine(intro)
                    if (conclusion.isNotBlank()) {
                        appendLine()
                        appendLine(conclusion)
                    }
                    appendLine()
                    appendLine("List 5 to 7 key takeaways from this document. For each one, bold the main insight and cite the page number. Focus on concrete facts, data, and conclusions.")
                }.trim()

                val citedPages = (firstChunks + lastChunks).map { it.pageNumber }.distinct().sorted()
                DocumentPromptResult(prompt, citedPages, intent)
            }

            // ------------------------------------------------------------------
            // SPECIFIC QA — relevant chunks only, simple direct question
            // ------------------------------------------------------------------
            DocumentIntent.SPECIFIC_QA -> {
                val relevantChunks = TfIdfExtractor.findRelevantChunks(
                    chunks = chunks,
                    query = rawUserQuery,
                    topK = 4
                )
                val context = DocumentChunker.buildContext(relevantChunks, maxChars = 2_800)
                val pageRefs = relevantChunks.map { it.pageNumber }.distinct().sorted()

                val prompt = buildString {
                    appendLine("The following is an excerpt from \"${doc.fileName}\" (pages ${pageRefs.joinToString(", ")}):")
                    appendLine()
                    appendLine(context)
                    appendLine()
                    appendLine("Question: $rawUserQuery")
                    appendLine()
                    appendLine("Answer based only on the text above. Cite page numbers for specific facts.")
                }.trim()

                DocumentPromptResult(prompt, pageRefs, intent)
            }
        }
    }
}
