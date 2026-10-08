package com.teja.gemmmobile

import com.teja.gemmmobile.ocr.DocumentIntent
import com.teja.gemmmobile.ocr.DocumentIntelligenceEngine
import com.teja.gemmmobile.ocr.DocumentPage
import com.teja.gemmmobile.ocr.ExtractedDocument
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class DocumentIntelligenceEngineTest {

    @Test
    fun testExtractHeadings() {
        val sampleText = """
            Chapter 1: Foundations of Deep Learning
            This chapter introduces neural networks.
            
            1.1 Perceptrons and Activation Functions
            A perceptron is the basic unit.
            
            UNSUPERVISED REPRESENTATION LEARNING
            Autoencoders belong to this category.
            
            Some ordinary body text that should not be a heading because it ends with a period.
        """.trimIndent()

        val headings = DocumentIntelligenceEngine.extractHeadings(sampleText)
        assertTrue(headings.any { it.contains("Chapter 1", ignoreCase = true) })
        assertTrue(headings.any { it.contains("1.1", ignoreCase = true) })
        assertTrue(headings.any { it.contains("UNSUPERVISED", ignoreCase = true) })
    }

    @Test
    fun testDetectIntent() {
        assertEquals(DocumentIntent.TOPIC_EXTRACTION, DocumentIntelligenceEngine.detectIntent("extract topics from this pdf"))
        assertEquals(DocumentIntent.TOPIC_EXTRACTION, DocumentIntelligenceEngine.detectIntent("table of contents"))
        assertEquals(DocumentIntent.TOPIC_EXTRACTION, DocumentIntelligenceEngine.detectIntent("show chapters and syllabus"))

        assertEquals(DocumentIntent.FULL_SUMMARY, DocumentIntelligenceEngine.detectIntent(""))
        assertEquals(DocumentIntent.FULL_SUMMARY, DocumentIntelligenceEngine.detectIntent("summarize this document"))
        assertEquals(DocumentIntent.FULL_SUMMARY, DocumentIntelligenceEngine.detectIntent("explain full pdf"))

        assertEquals(DocumentIntent.SPECIFIC_QA, DocumentIntelligenceEngine.detectIntent("what is reconstruction loss?"))
        assertEquals(DocumentIntent.SPECIFIC_QA, DocumentIntelligenceEngine.detectIntent("formula on page 14"))
    }

    @Test
    fun testSearchRelevantPages() {
        val pages = listOf(
            DocumentPage(pageNumber = 1, text = "Introduction to neural networks and artificial intelligence overview."),
            DocumentPage(pageNumber = 2, text = "Convolutional neural networks for computer vision and images."),
            DocumentPage(pageNumber = 3, text = "Autoencoder reconstruction loss is measured using mean squared error MSE formula."),
            DocumentPage(pageNumber = 4, text = "Reinforcement learning and Q-learning agents.")
        )

        val results = DocumentIntelligenceEngine.searchRelevantPages(pages, "reconstruction loss MSE", maxResults = 1)
        assertEquals(1, results.size)
        assertEquals(3, results[0].pageNumber)
    }

    @Test
    fun testBuildDocumentPromptTopicExtraction() {
        val pages = listOf(
            DocumentPage(pageNumber = 1, text = "Contents:\nChapter 1: Intro\nChapter 2: VAE", headings = listOf("Chapter 1: Intro", "Chapter 2: VAE")),
            DocumentPage(pageNumber = 15, text = "Chapter 2: VAE details", headings = listOf("Chapter 2: VAE details"))
        )
        val doc = ExtractedDocument(
            fileName = "ml_book.pdf",
            text = "Full book text",
            wordCount = 500,
            pageCount = 2,
            pages = pages
        )

        val result = DocumentIntelligenceEngine.buildDocumentPrompt(doc, "extract all topics")
        assertEquals(DocumentIntent.TOPIC_EXTRACTION, result.intent)
        assertTrue(result.promptForModel.contains("Table of Contents"))
        assertTrue(result.promptForModel.contains("ml_book.pdf"))
    }
}
