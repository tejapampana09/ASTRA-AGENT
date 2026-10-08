package com.teja.gemmmobile

import com.teja.gemmmobile.ocr.DocumentChunk
import com.teja.gemmmobile.ocr.DocumentChunker
import com.teja.gemmmobile.ocr.DocumentPage
import com.teja.gemmmobile.ocr.TfIdfExtractor
import org.junit.Assert.*
import org.junit.Test

class TfIdfExtractorTest {

    private fun makeChunk(text: String, page: Int, idx: Int) =
        DocumentChunk(text = text, pageNumber = page, chunkIndex = idx, wordCount = text.split(" ").size)

    @Test
    fun `extractTopics returns non-empty list for multi-chunk document`() {
        val chunks = listOf(
            makeChunk("Machine learning algorithms classification regression neural networks deep learning", 1, 0),
            makeChunk("Machine learning classification decision trees random forests ensemble methods", 1, 1),
            makeChunk("Neural networks backpropagation gradient descent optimization learning rate", 2, 2),
            makeChunk("Regression analysis linear regression logistic regression statistical models", 2, 3),
            makeChunk("Deep learning convolutional neural networks image recognition classification", 3, 4),
        )
        val topics = TfIdfExtractor.extractTopics(chunks, topN = 10, minDf = 2)
        assertTrue("Should return at least 3 topics", topics.size >= 3)
        val terms = topics.map { it.term.lowercase() }
        assertTrue("'classification' should be a top topic", terms.any { it.contains("classification") || it.contains("learning") })
    }

    @Test
    fun `findRelevantChunks returns chunks related to query`() {
        val chunks = listOf(
            makeChunk("Python programming variables loops functions", 1, 0),
            makeChunk("Machine learning classification neural networks training", 2, 1),
            makeChunk("Database SQL queries tables relationships joins", 3, 2),
            makeChunk("Neural networks backpropagation gradient descent epochs", 4, 3),
            makeChunk("Web development HTML CSS JavaScript frameworks", 5, 4),
        )
        val relevant = TfIdfExtractor.findRelevantChunks(chunks, "neural network training epochs", topK = 2)
        val pages = relevant.map { it.pageNumber }
        assertTrue("Neural network chunks should be returned", pages.any { it == 2 || it == 4 })
        assertTrue("Should return at most 2 chunks", relevant.size <= 2)
    }

    @Test
    fun `extractTopics handles single chunk without crash`() {
        val chunks = listOf(
            makeChunk("This is a simple document about nothing special", 1, 0)
        )
        // minDf=1 so single-chunk doc still returns results
        val topics = TfIdfExtractor.extractTopics(chunks, topN = 5, minDf = 1)
        assertNotNull(topics)
    }

    @Test
    fun `DocumentChunker splits long page into multiple chunks`() {
        val longText = (1..600).joinToString(" ") { "word$it" }
        val pages = listOf(DocumentPage(pageNumber = 1, text = longText))
        val chunks = DocumentChunker.chunk(pages)
        assertTrue("600 words should produce at least 2 chunks of 300", chunks.size >= 2)
        assertTrue("Each chunk should have ≤ 300 words", chunks.all { it.wordCount <= 300 })
        assertEquals("All chunks belong to page 1", chunks.all { it.pageNumber == 1 }, true)
    }

    @Test
    fun `DocumentChunker preserves page numbers across multiple pages`() {
        val pages = (1..5).map { p ->
            DocumentPage(pageNumber = p, text = (1..100).joinToString(" ") { "w${p}_$it" })
        }
        val chunks = DocumentChunker.chunk(pages)
        val pageSet = chunks.map { it.pageNumber }.toSet()
        assertEquals("Chunks should span all 5 pages", setOf(1, 2, 3, 4, 5), pageSet)
    }

    @Test
    fun `formatTopicsForPrompt produces numbered list`() {
        val chunks = listOf(
            makeChunk("artificial intelligence machine learning deep learning data science", 1, 0),
            makeChunk("artificial intelligence neural networks algorithms data science", 2, 1),
        )
        val topics = TfIdfExtractor.extractTopics(chunks, topN = 5, minDf = 1)
        val formatted = TfIdfExtractor.formatTopicsForPrompt(topics)
        assertTrue("Should start with '1.'", formatted.trimStart().startsWith("1."))
    }
}
