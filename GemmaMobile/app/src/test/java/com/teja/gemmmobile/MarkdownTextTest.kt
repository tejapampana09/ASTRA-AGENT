package com.teja.gemmmobile

import androidx.compose.ui.graphics.Color
import com.teja.gemmmobile.ui.buildInlineMarkdown
import com.teja.gemmmobile.ui.sanitizeMarkdown
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class MarkdownTextTest {

    @Test
    fun testSanitizeMathArtifacts() {
        val raw = "The answer is \$\\text{Gemma 4}\$ and \$\\mathrm{LiteRT}\$ with (\$\\text{fast}\$)."
        val sanitized = sanitizeMarkdown(raw)
        assertEquals("The answer is Gemma 4 and LiteRT with (fast).", sanitized)
    }

    @Test
    fun testBuildInlineMarkdownBoldAndCode() {
        val input = "Hello **world** with `code snippet` here."
        val annotated = buildInlineMarkdown(input, Color.Black, Color.LightGray)

        assertEquals("Hello world with  code snippet  here.", annotated.text)
        assertTrue(annotated.spanStyles.isNotEmpty())
    }

    @Test
    fun testSanitizeStandaloneTextWrapper() {
        val raw = "Value is \\text{Result} and \$x = y\$."
        val sanitized = sanitizeMarkdown(raw)
        assertEquals("Value is Result and x = y.", sanitized)
    }
}
