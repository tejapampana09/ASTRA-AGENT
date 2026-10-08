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
 * Intelligently routes document prompts between:
 * 1. Topic & Chapter Syllabus extraction (TOC & headings scan)
 * 2. Full Document Executive Summarization (Hierarchical Intro + Headings + Conclusion)
 * 3. Deep Specific Q&A with On-device Keyword/BM25 Page Retrieval & Page Citations
 */
object DocumentIntelligenceEngine {

    private const val TAG = "DocIntelligence"

    /**
     * Extracts probable section headings, chapter titles, and numbered topics from page text.
     */
    fun extractHeadings(pageText: String): List<String> {
        if (pageText.isBlank()) return emptyList()
        val lines = pageText.lines().map { it.trim() }.filter { it.isNotBlank() }
        val headings = mutableListOf<String>()

        val headingRegex = Regex("""^(?:Chapter|Section|Module|Part|Unit|\d+(?:\.\d+)*)\s+.*""", RegexOption.IGNORE_CASE)
        val shortTitleRegex = Regex("""^[A-Z0-9\s:–—\-]{3,60}$""")

        for (line in lines) {
            if (headingRegex.matches(line)) {
                headings.add(line.take(80))
            } else if (shortTitleRegex.matches(line) && line.length in 4..50 && !line.endsWith(".")) {
                headings.add(line.take(80))
            } else if (line.startsWith("#") || (line.startsWith("•") && line.contains("Chapter", ignoreCase = true))) {
                headings.add(line.removePrefix("#").trim().take(80))
            }
        }
        return headings.distinct().take(8)
    }

    /**
     * Detects user intent from their input text regarding the document.
     */
    fun detectIntent(query: String): DocumentIntent {
        val q = query.lowercase().trim()
        val topicKeywords = listOf(
            "topic", "topics", "index", "table of content", "toc", "syllabus",
            "chapters", "chapter", "outline", "list topics", "contents", "headings",
            "sections", "subtopics", "what are the topics", "show index"
        )
        if (topicKeywords.any { q.contains(it) }) {
            return DocumentIntent.TOPIC_EXTRACTION
        }

        val takeawaysKeywords = listOf(
            "takeaway", "takeaways", "key takeaways", "key findings", "highlights",
            "action items", "conclusions", "core insights", "key takeaway"
        )
        if (takeawaysKeywords.any { q.contains(it) }) {
            return DocumentIntent.KEY_TAKEAWAYS
        }

        val summaryKeywords = listOf(
            "summarize", "summary", "overview", "explain full", "explain all",
            "what is this", "what is this pdf", "about", "explain document",
            "explain this pdf", "main points", "tl;dr", "tldr"
        )
        if (q.isBlank() || summaryKeywords.any { q.contains(it) }) {
            return DocumentIntent.FULL_SUMMARY
        }

        return DocumentIntent.SPECIFIC_QA
    }

    /**
     * Scores and retrieves the top most relevant pages matching a specific user question
     * using on-device token frequency and keyword overlap (BM25-style relevance).
     */
    fun searchRelevantPages(pages: List<DocumentPage>, query: String, maxResults: Int = 3): List<DocumentPage> {
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

        if (queryKeywords.isEmpty()) {
            return pages.take(maxResults)
        }

        val scored = pages.map { page ->
            val pageLower = page.text.lowercase()
            var score = 0
            for (kw in queryKeywords) {
                // Exact word match
                val count = pageLower.split(kw).size - 1
                score += count * 2
                // Extra weight if keyword is in page headings
                if (page.headings.any { it.lowercase().contains(kw) }) {
                    score += 5
                }
            }
            Pair(page, score)
        }

        val sorted = scored.filter { it.second > 0 }.sortedByDescending { it.second }.map { it.first }
        return if (sorted.isNotEmpty()) sorted.take(maxResults) else pages.take(maxResults)
    }

    /**
     * Constructs a token-bounded, highly structured prompt for Gemma 4 E2B based on user intent.
     */
    fun buildDocumentPrompt(doc: ExtractedDocument, rawUserQuery: String): DocumentPromptResult {
        val intent = detectIntent(rawUserQuery)
        val pages = doc.pages.ifEmpty {
            listOf(DocumentPage(pageNumber = 1, text = doc.text))
        }

        return when (intent) {
            DocumentIntent.TOPIC_EXTRACTION -> {
                // Collect headings across all pages + index pages (pages 1-3)
                val headingLines = mutableListOf<String>()
                for (p in pages) {
                    for (h in p.headings) {
                        headingLines.add("Page ${p.pageNumber}: $h")
                    }
                }

                val indexExcerpts = pages.take(3).joinToString("\n\n") { p ->
                    "[Page ${p.pageNumber}]\n" + p.text.take(600)
                }

                val prompt = buildString {
                    appendLine("Document: \"${doc.fileName}\" (${doc.pageCount} Pages)")
                    appendLine("Task: Extract and list all academic/subject topics, chapters, and sections found inside this document.")
                    appendLine("CRITICAL RULE: Directly present the subject topics from the text. Do NOT discuss software, pipelines, AI, or document analysis architecture.")
                    appendLine()
                    if (headingLines.isNotEmpty()) {
                        appendLine("### Document Headings & Sections:")
                        headingLines.take(30).forEach { appendLine("• $it") }
                        appendLine()
                    }
                    if (indexExcerpts.isNotBlank()) {
                        appendLine("### Document Opening Pages Excerpt:")
                        appendLine(indexExcerpts.take(1200))
                        appendLine()
                    }
                    appendLine("### Request: " + (if (rawUserQuery.isNotBlank()) rawUserQuery else "Extract all topics and sections from this document."))
                    appendLine()
                    appendLine("### Instructions:")
                    appendLine("1. Present a clear, hierarchically organized Table of Contents / Topic Syllabus based on the document's content.")
                    appendLine("2. Group topics under clear section/chapter headers with page citations (e.g. [Page X]).")
                    appendLine("3. Provide a brief 1-line summary of what each topic covers in the document.")
                    appendLine("4. Conclude by asking which topic the user would like to dive into first.")
                }.trim()

                DocumentPromptResult(
                    promptForModel = prompt,
                    citedPages = pages.take(3).map { it.pageNumber },
                    intent = intent
                )
            }

            DocumentIntent.FULL_SUMMARY -> {
                val introText = pages.take(2).joinToString("\n\n") { p ->
                    "[Page ${p.pageNumber}]: " + p.text.take(500)
                }
                val lastPages = if (pages.size > 2) pages.takeLast(2) else emptyList()
                val conclusionText = lastPages.joinToString("\n\n") { p ->
                    "[Page ${p.pageNumber}]: " + p.text.take(400)
                }
                val allHeadings = pages.flatMap { p -> p.headings.map { "Page ${p.pageNumber}: $it" } }.take(15)

                val prompt = buildString {
                    appendLine("Document: \"${doc.fileName}\" (${doc.pageCount} Pages)")
                    appendLine("Task: Provide a comprehensive executive summary of this document.")
                    appendLine("CRITICAL RULE: Directly summarize the subject matter of the document. Do NOT discuss document processing systems, OCR, or analysis pipelines.")
                    appendLine()
                    appendLine("### Introduction Excerpt:")
                    appendLine(introText)
                    appendLine()
                    if (allHeadings.isNotEmpty()) {
                        appendLine("### Key Headings Covered:")
                        allHeadings.forEach { appendLine("• $it") }
                        appendLine()
                    }
                    if (conclusionText.isNotBlank()) {
                        appendLine("### Conclusion / Summary Excerpt:")
                        appendLine(conclusionText)
                        appendLine()
                    }
                    appendLine("### Instructions:")
                    appendLine("Provide a comprehensive executive summary in ChatGPT style:")
                    appendLine("1. **Core Purpose**: 1-2 sentences on what this document is about.")
                    appendLine("2. **Key Concepts & Findings**: 3-5 structured bullet points highlighting the main ideas.")
                    appendLine("3. **Key Takeaway**: A crisp concluding takeaway.")
                    appendLine("4. Conclude by suggesting 2 specific sections the user can explore next.")
                }.trim()

                DocumentPromptResult(
                    promptForModel = prompt,
                    citedPages = (pages.take(2) + lastPages).map { it.pageNumber }.distinct(),
                    intent = intent
                )
            }

            DocumentIntent.KEY_TAKEAWAYS -> {
                val introText = pages.take(2).joinToString("\n\n") { p ->
                    "[Page ${p.pageNumber}]: " + p.text.take(450)
                }
                val lastPages = if (pages.size > 2) pages.takeLast(2) else emptyList()
                val conclusionText = lastPages.joinToString("\n\n") { p ->
                    "[Page ${p.pageNumber}]: " + p.text.take(400)
                }
                val prompt = buildString {
                    appendLine("Document: \"${doc.fileName}\" (${doc.pageCount} Pages)")
                    appendLine("Task: Extract the most crucial Key Takeaways, Core Findings, and Actionable Insights.")
                    appendLine("CRITICAL RULE: Directly state the key takeaways from the document content. Do NOT discuss software, OCR, or document parsing.")
                    appendLine()
                    if (introText.isNotBlank()) {
                        appendLine("### Document Context:")
                        appendLine(introText)
                        appendLine()
                    }
                    if (conclusionText.isNotBlank()) {
                        appendLine("### Key Highlights / Conclusions:")
                        appendLine(conclusionText)
                        appendLine()
                    }
                    appendLine("### Instructions:")
                    appendLine("Provide 5 to 7 sharp, high-impact bullet points capturing the core insights and findings:")
                    appendLine("1. Bold the core insight for each point (e.g., • **Finding**: Explanation).")
                    appendLine("2. Include page citations [Page X] where available.")
                    appendLine("3. Focus on concrete data, numbers, conclusions, and decisions.")
                }.trim()

                DocumentPromptResult(
                    promptForModel = prompt,
                    citedPages = (pages.take(2) + lastPages).map { it.pageNumber }.distinct(),
                    intent = intent
                )
            }

            DocumentIntent.SPECIFIC_QA -> {
                val relevantPages = searchRelevantPages(pages, rawUserQuery, maxResults = 3)
                val excerpts = relevantPages.joinToString("\n\n") { p ->
                    "--- Page ${p.pageNumber} ---\n${p.text.take(800)}"
                }

                val prompt = buildString {
                    appendLine("Attached Document: \"${doc.fileName}\" (Relevant Excerpts from Pages ${relevantPages.map { it.pageNumber }.joinToString(", ")})")
                    appendLine()
                    appendLine(excerpts)
                    appendLine()
                    appendLine("User Question: $rawUserQuery")
                    appendLine()
                    appendLine("Instructions:")
                    appendLine("Answer the user's question clearly, thoroughly, and directly based on the document excerpts above.")
                    appendLine("Explicitly cite page numbers (e.g., [Page X]) for all specific facts, formulas, or claims.")
                }.trim()

                DocumentPromptResult(
                    promptForModel = prompt,
                    citedPages = relevantPages.map { it.pageNumber },
                    intent = intent
                )
            }
        }
    }
}
