package com.teja.gemmmobile.ocr

/**
 * Pure-Kotlin TF-IDF topic extractor and chunk retriever.
 *
 * Two primary uses:
 *  1. [extractTopics] — scans ALL chunks (no token limit!) and returns the top N meaningful
 *     topics/keywords ranked by TF-IDF weight. Covers entire 100-page PDF instantly.
 *  2. [findRelevantChunks] — for a user query, returns the top K chunks most likely to
 *     contain the answer (keyword-overlap + TF-IDF boost).
 *
 * No Android dependencies. No model calls. Pure math on raw text.
 */
data class TopicResult(
    val term: String,
    val score: Double,
    val pageNumbers: List<Int>         // which pages mention this term most
)

object TfIdfExtractor {

    // -----------------------------------------------------------------------
    // Stop-word list — common English words that carry no topic signal
    // -----------------------------------------------------------------------
    private val STOP_WORDS = setOf(
        "the", "a", "an", "is", "it", "in", "on", "at", "to", "for", "of", "and", "or", "but",
        "with", "this", "that", "are", "was", "be", "have", "has", "had", "will", "would",
        "could", "should", "from", "by", "as", "its", "their", "they", "we", "you", "he",
        "she", "i", "my", "your", "our", "not", "all", "also", "about", "more", "so", "if",
        "can", "do", "did", "been", "than", "then", "there", "when", "which", "who", "what",
        "how", "any", "each", "into", "through", "after", "before", "between", "such", "these",
        "those", "some", "other", "very", "just", "only", "over", "up", "out", "no", "one",
        "two", "three", "four", "five", "first", "second", "third", "may", "use", "used",
        "using", "given", "based", "called", "following", "since", "while", "where", "here",
        "see", "say", "said", "get", "make", "new", "well", "way", "per", "et", "al", "fig",
        "figure", "table", "page", "pages", "chapter", "section", "note", "example", "above",
        "below", "thus", "hence", "therefore", "however", "although", "whereas", "moreover",
        "furthermore", "ii", "iii", "iv", "vi", "vii", "viii", "ix", "xi", "xii"
    )

    // Regex to tokenise text into words (letters/digits, length >= 3)
    private val WORD_REGEX = Regex("""[a-zA-Z][a-zA-Z0-9]{2,}""")

    // -----------------------------------------------------------------------
    // Public API
    // -----------------------------------------------------------------------

    /**
     * Extracts the top [topN] topics from ALL [chunks] using TF-IDF scoring.
     *
     * This runs on the complete document — no token ceiling applies here.
     * Typical runtime: < 200 ms for a 100-page PDF on a mid-range Android device.
     *
     * @param chunks   Full list of chunks from [DocumentChunker.chunk]
     * @param topN     How many topics to return (default 25)
     * @param minDf    Minimum document (chunk) frequency for a term to be considered a topic
     */
    fun extractTopics(
        chunks: List<DocumentChunk>,
        topN: Int = 25,
        minDf: Int = 2
    ): List<TopicResult> {
        if (chunks.isEmpty()) return emptyList()

        val N = chunks.size.toDouble()

        // --- Step 1: Term frequency per chunk ---
        // chunkTf[chunkIndex] = Map<term, rawCount>
        val chunkTf: List<Map<String, Int>> = chunks.map { chunk ->
            termFrequency(chunk.text)
        }

        // --- Step 2: Document frequency (how many chunks contain each term) ---
        val df = mutableMapOf<String, Int>()
        for (tf in chunkTf) {
            for (term in tf.keys) {
                df[term] = (df[term] ?: 0) + 1
            }
        }

        // --- Step 3: Bigrams (two-word phrases) across all chunks ---
        val bigramDf = mutableMapOf<String, Int>()
        val bigramPages = mutableMapOf<String, MutableSet<Int>>()
        for ((idx, chunk) in chunks.withIndex()) {
            val bigrams = extractBigrams(chunk.text)
            val seen = mutableSetOf<String>()
            for (bg in bigrams) {
                if (seen.add(bg)) {
                    bigramDf[bg] = (bigramDf[bg] ?: 0) + 1
                    bigramPages.getOrPut(bg) { mutableSetOf() }.add(chunk.pageNumber)
                }
            }
        }

        // --- Step 4: TF-IDF score per term ---
        val termScore = mutableMapOf<String, Double>()
        val termPages = mutableMapOf<String, MutableSet<Int>>()

        for ((idx, tf) in chunkTf.withIndex()) {
            val chunk = chunks[idx]
            val maxCount = tf.values.maxOrNull()?.toDouble() ?: 1.0
            for ((term, count) in tf) {
                val docFreq = df[term] ?: 1
                if (docFreq < minDf) continue           // too rare → skip
                if (docFreq > N * 0.85) continue        // too common → skip (stop-word-like)
                val normTf = count / maxCount
                val idf = Math.log((N + 1) / (docFreq + 1)) + 1.0
                val score = normTf * idf
                termScore[term] = (termScore[term] ?: 0.0) + score
                termPages.getOrPut(term) { mutableSetOf() }.add(chunk.pageNumber)
            }
        }

        // --- Step 5: Include high-quality bigrams (boost score x1.5) ---
        for ((bg, docFreq) in bigramDf) {
            if (docFreq < minDf) continue
            val idf = Math.log((N + 1) / (docFreq + 1)) + 1.0
            val bigramScore = docFreq * idf * 1.5
            termScore[bg] = (termScore[bg] ?: 0.0) + bigramScore
            termPages.getOrPut(bg) { mutableSetOf() }.addAll(bigramPages[bg] ?: emptySet())
        }

        // --- Step 6: Sort and return top N ---
        return termScore.entries
            .sortedByDescending { it.value }
            .take(topN)
            .map { (term, score) ->
                TopicResult(
                    term = term.replaceFirstChar { it.uppercase() },
                    score = score,
                    pageNumbers = (termPages[term] ?: emptySet<Int>())
                        .sorted()
                        .take(5)
                )
            }
    }

    /**
     * Retrieves the top [topK] chunks most relevant to the given [query].
     *
     * Uses keyword overlap + TF-IDF boost so that chunks with rare-but-matching terms
     * rank higher than chunks with very common terms.
     *
     * @param chunks   Full chunk list
     * @param query    Raw user query string
     * @param topK     How many chunks to return (default 4 → fits ~1200 tokens of content)
     */
    fun findRelevantChunks(
        chunks: List<DocumentChunk>,
        query: String,
        topK: Int = 4
    ): List<DocumentChunk> {
        if (chunks.isEmpty()) return emptyList()
        if (chunks.size <= topK) return chunks

        val queryTerms = WORD_REGEX.findAll(query.lowercase())
            .map { it.value }
            .filter { it !in STOP_WORDS }
            .toSet()

        if (queryTerms.isEmpty()) return chunks.take(topK)

        val N = chunks.size.toDouble()

        // Build IDF for query terms only (faster)
        val df = mutableMapOf<String, Int>()
        for (chunk in chunks) {
            val words = WORD_REGEX.findAll(chunk.text.lowercase()).map { it.value }.toSet()
            for (qt in queryTerms) {
                if (qt in words) df[qt] = (df[qt] ?: 0) + 1
            }
        }

        val scored = chunks.map { chunk ->
            val chunkLower = chunk.text.lowercase()
            val chunkWords = WORD_REGEX.findAll(chunkLower).map { it.value }.toList()
            val wordSet = chunkWords.toSet()
            val maxCount = chunkWords.groupingBy { it }.eachCount().values.maxOrNull()?.toDouble() ?: 1.0

            var score = 0.0
            for (qt in queryTerms) {
                val count = chunkWords.count { it == qt }
                if (count == 0) continue
                val normTf = count / maxCount
                val idf = Math.log((N + 1) / ((df[qt] ?: 1) + 1)) + 1.0
                score += normTf * idf
                // Extra boost for heading matches
                if (chunk.text.lines().any { line ->
                        line.trim().let { it.length < 80 && it.lowercase().contains(qt) }
                    }) {
                    score += idf * 0.5
                }
            }
            Pair(chunk, score)
        }

        return scored
            .filter { it.second > 0 }
            .sortedByDescending { it.second }
            .take(topK)
            .map { it.first }
            .sortedBy { it.pageNumber }          // re-sort by page for readable context
            .ifEmpty { chunks.take(topK) }
    }

    /**
     * Formats the top topic results into a concise, human-readable topic syllabus string.
     * This string is injected into the model prompt for nice formatting.
     *
     * Token cost: ~200–300 tokens for 25 topics.
     */
    fun formatTopicsForPrompt(topics: List<TopicResult>): String {
        if (topics.isEmpty()) return "(No significant topics detected)"
        val sb = StringBuilder()
        topics.forEachIndexed { i, t ->
            val pages = if (t.pageNumbers.isNotEmpty()) " [Pages ${t.pageNumbers.joinToString(", ")}]" else ""
            sb.appendLine("${i + 1}. ${t.term}$pages")
        }
        return sb.toString().trim()
    }

    // -----------------------------------------------------------------------
    // Internal helpers
    // -----------------------------------------------------------------------

    /** Raw term-frequency map for a block of text. Excludes stop-words and short words. */
    private fun termFrequency(text: String): Map<String, Int> {
        val counts = mutableMapOf<String, Int>()
        for (match in WORD_REGEX.findAll(text.lowercase())) {
            val word = match.value
            if (word in STOP_WORDS) continue
            counts[word] = (counts[word] ?: 0) + 1
        }
        return counts
    }

    /**
     * Extracts meaningful two-word bigrams from a text block.
     * Both words must be non-stop-words of length >= 3.
     */
    fun extractBigrams(text: String): List<String> {
        val words = WORD_REGEX.findAll(text.lowercase())
            .map { it.value }
            .filter { it !in STOP_WORDS && it.length >= 4 }
            .toList()

        val bigrams = mutableListOf<String>()
        for (i in 0 until words.size - 1) {
            bigrams.add("${words[i]} ${words[i + 1]}")
        }
        return bigrams
    }
}
