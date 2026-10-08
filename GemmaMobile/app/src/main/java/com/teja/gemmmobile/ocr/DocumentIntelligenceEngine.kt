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
 * Intent routing:
 * ┌─────────────────┬───────────────────────────────────────────────────────┐
 * │ TOPIC_EXTRACTION│ TF-IDF over ALL chunks → no token limit, instant      │
 * │ FULL_SUMMARY    │ First 3 pages intro + last 2 pages conclusion          │
 * │ KEY_TAKEAWAYS   │ First 2 + last 2 pages (intro + conclusion)            │
 * │ SPECIFIC_QA     │ TF-IDF chunk retrieval → top 4 relevant chunks        │
 * └─────────────────┴───────────────────────────────────────────────────────┘
 *
 * Token budget: all content passed to the model is bounded to ~1 200 chars of
 * document text (≈ 400 tokens), leaving ~1 600 tokens for prompt overhead and
 * the model's response within the 2 048-token ceiling.
 */
object DocumentIntelligenceEngine {

    private const val TAG = "DocIntelligence"

    // Max chars of document content injected per prompt (≈ 400 tokens)
    private const val MAX_CONTENT_CHARS = 3_000

    // -----------------------------------------------------------------------
    // Heading extractor (used by OCR helper during ingestion)
    // -----------------------------------------------------------------------

    fun extractHeadings(pageText: String): List<String> {
        if (pageText.isBlank()) return emptyList()
        val lines = pageText.lines().map { it.trim() }.filter { it.isNotBlank() }
        val headings = mutableListOf<String>()

        val headingRegex = Regex("""^(?:Chapter|Section|Module|Part|Unit|\d+(?:\.\d+)*)\s+.*""", RegexOption.IGNORE_CASE)
        val shortTitleRegex = Regex("""^[A-Z0-9\s:–—\-]{3,60}$""")

        for (line in lines) {
            when {
                headingRegex.matches(line) -> headings.add(line.take(80))
                shortTitleRegex.matches(line) && line.length in 4..50 && !line.endsWith(".") ->
                    headings.add(line.take(80))
                line.startsWith("#") || (line.startsWith("•") && line.contains("Chapter", ignoreCase = true)) ->
                    headings.add(line.removePrefix("#").trim().take(80))
            }
        }
        return headings.distinct().take(8)
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
    // Main prompt builder
    // -----------------------------------------------------------------------

    fun buildDocumentPrompt(doc: ExtractedDocument, rawUserQuery: String): DocumentPromptResult {
        val intent = detectIntent(rawUserQuery)
        val pages = doc.pages.ifEmpty {
            listOf(DocumentPage(pageNumber = 1, text = doc.text))
        }
        // Use pre-built chunks if available; otherwise build on the fly
        val chunks = doc.chunks.ifEmpty { DocumentChunker.chunk(pages) }

        Log.d(TAG, "intent=$intent pages=${pages.size} chunks=${chunks.size} query='$rawUserQuery'")

        return when (intent) {

            // ------------------------------------------------------------------
            // TOPIC EXTRACTION — TF-IDF on ALL chunks, zero token limit issue
            // ------------------------------------------------------------------
            DocumentIntent.TOPIC_EXTRACTION -> {
                val topics = TfIdfExtractor.extractTopics(chunks, topN = 25)
                val topicsText = TfIdfExtractor.formatTopicsForPrompt(topics)

                // Also gather any structural headings found during ingestion
                val headingLines = pages
                    .flatMap { p -> p.headings.map { "Page ${p.pageNumber}: $it" } }
                    .distinct()
                    .take(20)

                val prompt = buildString {
                    appendLine("Document: \"${doc.fileName}\" (${doc.pageCount} pages, ${doc.wordCount} words)")
                    appendLine("Task: Present a structured, readable Topic Index / Syllabus from this document.")
                    appendLine("RULE: List the document's own subject matter topics directly. Do NOT discuss software, AI, or PDF processing.")
                    appendLine()
                    appendLine("### Top Topics Detected Across All ${doc.pageCount} Pages (TF-IDF ranked):")
                    appendLine(topicsText)
                    if (headingLines.isNotEmpty()) {
                        appendLine()
                        appendLine("### Section Headings Found:")
                        headingLines.forEach { appendLine("• $it") }
                    }
                    appendLine()
                    appendLine("### Instructions:")
                    appendLine("Using the topics and headings above, produce a clean, numbered Topic Syllabus:")
                    appendLine("1. Group related topics under clear Section/Chapter headers.")
                    appendLine("2. Include page references [Page X] wherever available.")
                    appendLine("3. Add a 1-line description of what each topic covers.")
                    appendLine("4. Ask the user which topic they'd like to explore first.")
                }.trim()

                val citedPages = topics.flatMap { it.pageNumbers }.distinct().sorted().take(10)
                DocumentPromptResult(prompt, citedPages, intent)
            }

            // ------------------------------------------------------------------
            // FULL SUMMARY — intro pages + conclusion pages (token-safe)
            // ------------------------------------------------------------------
            DocumentIntent.FULL_SUMMARY -> {
                val firstChunks = DocumentChunker.chunksForFirstPages(chunks, pageCount = 3)
                    .take(4)
                val lastChunks = if (pages.size > 3)
                    DocumentChunker.chunksForLastPages(chunks, pageCount = 2).take(2)
                else emptyList()

                val introText = DocumentChunker.buildContext(firstChunks, maxChars = 2_000)
                val conclusionText = DocumentChunker.buildContext(lastChunks, maxChars = 1_000)
                val allHeadings = pages.flatMap { p -> p.headings.map { "Page ${p.pageNumber}: $it" } }.take(15)

                val prompt = buildString {
                    appendLine("Document: \"${doc.fileName}\" (${doc.pageCount} pages)")
                    appendLine("Task: Provide a comprehensive executive summary of this document.")
                    appendLine("RULE: Summarize the subject matter directly. Do NOT discuss OCR, analysis pipelines, or software.")
                    appendLine()
                    appendLine("### Document Opening (Pages 1–3):")
                    appendLine(introText)
                    if (allHeadings.isNotEmpty()) {
                        appendLine()
                        appendLine("### Key Section Headings:")
                        allHeadings.forEach { appendLine("• $it") }
                    }
                    if (conclusionText.isNotBlank()) {
                        appendLine()
                        appendLine("### Document Conclusion / Final Pages:")
                        appendLine(conclusionText)
                    }
                    appendLine()
                    appendLine("### Instructions — ChatGPT-style executive summary:")
                    appendLine("1. **Core Purpose**: 1–2 sentences on what this document is about.")
                    appendLine("2. **Key Concepts & Findings**: 3–5 structured bullet points.")
                    appendLine("3. **Key Takeaway**: One crisp concluding statement.")
                    appendLine("4. Suggest 2 specific topics the user can explore next.")
                }.trim()

                val citedPages = (firstChunks + lastChunks).map { it.pageNumber }.distinct().sorted()
                DocumentPromptResult(prompt, citedPages, intent)
            }

            // ------------------------------------------------------------------
            // KEY TAKEAWAYS — intro + conclusion pages
            // ------------------------------------------------------------------
            DocumentIntent.KEY_TAKEAWAYS -> {
                val firstChunks = DocumentChunker.chunksForFirstPages(chunks, pageCount = 2).take(3)
                val lastChunks = if (pages.size > 2)
                    DocumentChunker.chunksForLastPages(chunks, pageCount = 2).take(2)
                else emptyList()

                val introText = DocumentChunker.buildContext(firstChunks, maxChars = 1_500)
                val conclusionText = DocumentChunker.buildContext(lastChunks, maxChars = 1_000)

                val prompt = buildString {
                    appendLine("Document: \"${doc.fileName}\" (${doc.pageCount} pages)")
                    appendLine("Task: Extract the most crucial Key Takeaways, Core Findings, and Actionable Insights.")
                    appendLine("RULE: State key takeaways directly from the document content. Do NOT discuss software, OCR, or document parsing.")
                    appendLine()
                    if (introText.isNotBlank()) {
                        appendLine("### Document Context (Opening):")
                        appendLine(introText)
                        appendLine()
                    }
                    if (conclusionText.isNotBlank()) {
                        appendLine("### Key Highlights / Conclusions:")
                        appendLine(conclusionText)
                        appendLine()
                    }
                    appendLine("### Instructions:")
                    appendLine("Provide 5 to 7 sharp, high-impact bullet points capturing the core insights:")
                    appendLine("1. Bold the core insight for each point (e.g., • **Finding**: Explanation).")
                    appendLine("2. Include page citations [Page X] where available.")
                    appendLine("3. Focus on concrete data, numbers, conclusions, and decisions.")
                }.trim()

                val citedPages = (firstChunks + lastChunks).map { it.pageNumber }.distinct().sorted()
                DocumentPromptResult(prompt, citedPages, intent)
            }

            // ------------------------------------------------------------------
            // SPECIFIC QA — TF-IDF chunk retrieval → only relevant pages passed
            // ------------------------------------------------------------------
            DocumentIntent.SPECIFIC_QA -> {
                val relevantChunks = TfIdfExtractor.findRelevantChunks(
                    chunks = chunks,
                    query = rawUserQuery,
                    topK = 4
                )
                val context = DocumentChunker.buildContext(relevantChunks, maxChars = MAX_CONTENT_CHARS)
                val pageRefs = relevantChunks.map { it.pageNumber }.distinct().sorted()

                val prompt = buildString {
                    appendLine("Document: \"${doc.fileName}\" — Relevant excerpts from pages ${pageRefs.joinToString(", ")} (of ${doc.pageCount} total):")
                    appendLine()
                    appendLine(context)
                    appendLine()
                    appendLine("User Question: $rawUserQuery")
                    appendLine()
                    appendLine("Instructions:")
                    appendLine("Answer the question clearly and thoroughly based only on the excerpts above.")
                    appendLine("Cite page numbers (e.g., [Page X]) for every specific fact, formula, or claim.")
                    appendLine("If the answer is not in the excerpts, say so and suggest asking about a specific section.")
                }.trim()

                DocumentPromptResult(prompt, pageRefs, intent)
            }
        }
    }
}
