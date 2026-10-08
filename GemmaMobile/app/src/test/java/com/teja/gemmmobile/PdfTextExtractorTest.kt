package com.teja.gemmmobile

import com.teja.gemmmobile.ocr.PdfTextExtractor
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class PdfTextExtractorTest {

    @Test
    fun testParseContentStreamSimpleTj() {
        val stream = """
            BT
            /F1 12 Tf
            (Hello World from PDF!) Tj
            ET
        """.trimIndent()

        val parsed = PdfTextExtractor.parseContentStream(stream)
        assertEquals("Hello World from PDF!", parsed)
    }

    @Test
    fun testParseContentStreamKerningArrayTJ() {
        val stream = """
            BT
            /F1 12 Tf
            [(Machine ) -120 (Learning) -150 (Foundations)] TJ
            ET
        """.trimIndent()

        val parsed = PdfTextExtractor.parseContentStream(stream)
        assertTrue(parsed.contains("Machine"))
        assertTrue(parsed.contains("Learning"))
        assertTrue(parsed.contains("Foundations"))
    }

    @Test
    fun testExtractTextFromSyntheticPdf() {
        val streamContent = "BT /F1 12 Tf (Chapter 1: Neural Networks and Deep Learning Introduction) Tj T* (This book explores transformers and attention mechanisms.) Tj ET"
        val syntheticPdf = """
            %PDF-1.4
            1 0 obj
            << /Type /Catalog /Pages 2 0 R >>
            endobj
            2 0 obj
            << /Type /Pages /Kids [3 0 R] /Count 1 >>
            endobj
            3 0 obj
            << /Type /Page /Parent 2 0 R /Contents 4 0 R >>
            endobj
            4 0 obj
            << /Length ${streamContent.length} >>
            stream
            $streamContent
            endstream
            endobj
            trailer
            << /Root 1 0 R >>
            %%EOF
        """.trimIndent()

        val pages = PdfTextExtractor.extractText(syntheticPdf.toByteArray(Charsets.ISO_8859_1), expectedPageCount = 1)
        assertTrue("Should extract digital text", pages.isNotEmpty())
        assertTrue(pages[0].text.contains("Neural Networks"))
        assertTrue(pages[0].headings.any { it.contains("Chapter 1") })
    }
}
