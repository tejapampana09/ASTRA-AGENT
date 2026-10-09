package com.teja.gemmmobile.ui

import android.widget.Toast
import com.teja.gemmmobile.search.SearchResult
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.size
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material3.Icon
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.runtime.LaunchedEffect
import kotlinx.coroutines.delay
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.material3.HorizontalDivider
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.ClickableText
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

private val REGEX_CODE_BLOCK = Regex("""```([a-zA-Z0-9_+#.-]*)\s*\n([\s\S]*?)```""")
private val REGEX_UNCLOSED_CODE = Regex("""```([a-zA-Z0-9_+#.-]*)\s*\n([\s\S]*)""")
private val REGEX_TABLE = Regex("""(?m)^([ \t]*\|[^\n]+\|[ \t]*\n[ \t]*\|[-: |]+\|[ \t]*(?:\n[ \t]*\|[^\n]+\|[ \t]*)+)""")
private val REGEX_TEXT_1 = Regex("""\$\s*\\text\{([^}]+)\}\s*\$""")
private val REGEX_TEXT_2 = Regex("""\$\s*\\mathrm\{([^}]+)\}\s*\$""")
private val REGEX_TEXT_3 = Regex("""\(\s*\\text\{([^}]+)\}\s*\)""")
private val REGEX_TEXT_4 = Regex("""\\text\{([^}]+)\}""")
private val REGEX_TEXT_5 = Regex("""\$([^$\n]+)\$""")
private val REGEX_NUMBERED_LIST = Regex("""^\d+\.\s+.*""")
private val REGEX_HTML_LINK = Regex("""<a\s+(?:[^>]*?\s+)?href=["']([^"']+)["'][^>]*>(.*?)<\/a>""", RegexOption.IGNORE_CASE)
private val REGEX_RAW_HREF = Regex("""href=["'](https?://[^"']+)["']""", RegexOption.IGNORE_CASE)
private val REGEX_HTML_SELF_CLOSING = Regex("""<a\s+(?:[^>]*?\s+)?href=["']([^"']+)["'][^>]*\/?>""", RegexOption.IGNORE_CASE)

private val markdownBlockCache = android.util.LruCache<String, List<MarkdownBlock>>(300)
private val renderedLineCache = android.util.LruCache<String, List<RenderedLine>>(400)

sealed class MarkdownBlock {
    data class Code(val language: String, val code: String) : MarkdownBlock()
    data class Table(val headers: List<String>, val rows: List<List<String>>) : MarkdownBlock()
    data class Text(val content: String) : MarkdownBlock()
}

/**
 * Renders formatted Markdown content cleanly in Jetpack Compose:
 * - Syntax-highlighted code blocks with ChatGPT-style top bar and Copy button
 * - Scrollable, copyable ChatGPT-style tables
 * - Clickable links (both [Markdown](http...) and raw http/https URLs) that launch the browser
 * - Cleans up LaTeX math symbols ($\text{...}$, etc.)
 * - Formats #, ## and ### headings
 * - Formats bullet lists (* or -) and numbered lists (1.)
 * - Formats **bold**, *italic*, and `code` inline spans cleanly without raw symbols
 */
@Composable
fun MarkdownText(
    text: String,
    isUser: Boolean,
    modifier: Modifier = Modifier,
    overrideTextColor: Color? = null,
    searchResults: List<SearchResult> = emptyList()
) {
    val textColor = overrideTextColor ?: if (isUser) {
        MaterialTheme.colorScheme.onPrimaryContainer
    } else {
        Color(0xFFECECEC)
    }

    val linkColor = if (isUser) {
        MaterialTheme.colorScheme.primary
    } else {
        Color(0xFF58A6FF) // Crisp high-contrast link blue (ChatGPT dark mode style)
    }

    val codeBgColor = if (isUser) {
        MaterialTheme.colorScheme.primary.copy(alpha = 0.15f)
    } else {
        Color(0xFF262628)
    }

    val blocks = remember(text) { parseMarkdownBlocks(text) }

    Column(
        modifier = modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        for (block in blocks) {
            when (block) {
                is MarkdownBlock.Code -> {
                    CodeBlockView(
                        language = block.language,
                        code = block.code
                    )
                }
                is MarkdownBlock.Table -> {
                    MarkdownTableView(
                        headers = block.headers,
                        rows = block.rows
                    )
                }
                is MarkdownBlock.Text -> {
                    TextBlockView(
                        content = block.content,
                        textColor = textColor,
                        linkColor = linkColor,
                        codeBgColor = codeBgColor,
                        searchResults = searchResults
                    )
                }
            }
        }
    }
}

private sealed class RenderedLine {
    object Blank : RenderedLine()
    data class Header(val annotatedText: AnnotatedString, val level: Int) : RenderedLine()
    data class Bullet(
        val prefix: String,
        val annotatedText: AnnotatedString,
        val isSectionHeader: Boolean = false,
        val indentLevel: Int = 0
    ) : RenderedLine()
    data class Paragraph(val annotatedText: AnnotatedString) : RenderedLine()
}

private fun parseMarkdownLines(
    content: String,
    textColor: Color,
    linkColor: Color,
    codeBgColor: Color,
    searchResults: List<SearchResult> = emptyList()
): List<RenderedLine> {
    val sanitized = sanitizeMarkdown(content, searchResults)
    val rawLines = sanitized.lines()
    val result = mutableListOf<RenderedLine>()

    for ((index, line) in rawLines.withIndex()) {
        val trimmed = line.trim()
        if (trimmed.isEmpty()) {
            if (index > 0 && index < rawLines.size - 1) {
                result.add(RenderedLine.Blank)
            }
            continue
        }

        val indentLevel = (line.takeWhile { it.isWhitespace() }.length / 2).coerceIn(0, 3)

        when {
            trimmed.startsWith("### ") -> {
                result.add(
                    RenderedLine.Header(
                        annotatedText = buildInlineMarkdown(trimmed.removePrefix("### ").trim(), textColor, linkColor, codeBgColor),
                        level = 3
                    )
                )
            }
            trimmed.startsWith("## ") -> {
                result.add(
                    RenderedLine.Header(
                        annotatedText = buildInlineMarkdown(trimmed.removePrefix("## ").trim(), textColor, linkColor, codeBgColor),
                        level = 2
                    )
                )
            }
            trimmed.startsWith("# ") -> {
                result.add(
                    RenderedLine.Header(
                        annotatedText = buildInlineMarkdown(trimmed.removePrefix("# ").trim(), textColor, linkColor, codeBgColor),
                        level = 1
                    )
                )
            }
            trimmed.startsWith("* ") || trimmed.startsWith("- ") || trimmed.startsWith("• ") -> {
                val c = when {
                    trimmed.startsWith("* ") -> trimmed.removePrefix("* ")
                    trimmed.startsWith("- ") -> trimmed.removePrefix("- ")
                    else -> trimmed.removePrefix("• ")
                }.trim()
                result.add(
                    RenderedLine.Bullet(
                        prefix = "•",
                        annotatedText = buildInlineMarkdown(c, textColor, linkColor, codeBgColor),
                        isSectionHeader = false,
                        indentLevel = indentLevel
                    )
                )
            }
            trimmed.matches(REGEX_NUMBERED_LIST) -> {
                val prefix = trimmed.substringBefore(". ") + "."
                val c = trimmed.substringAfter(". ").trim()
                val isSectionHeader = (c.length >= 3 && c.all { it.isUpperCase() || it.isWhitespace() || it == '&' || it == '-' || it == '_' || it == '/' }) ||
                        (c.startsWith("**") && c.endsWith("**"))
                result.add(
                    RenderedLine.Bullet(
                        prefix = prefix,
                        annotatedText = buildInlineMarkdown(c, textColor, linkColor, codeBgColor),
                        isSectionHeader = isSectionHeader,
                        indentLevel = indentLevel
                    )
                )
            }
            else -> {
                result.add(
                    RenderedLine.Paragraph(
                        annotatedText = buildInlineMarkdown(trimmed, textColor, linkColor, codeBgColor)
                    )
                )
            }
        }
    }
    return result
}

@Composable
private fun RenderMarkdownLine(line: RenderedLine) {
    when (line) {
        is RenderedLine.Blank -> {
            Spacer(modifier = Modifier.height(8.dp))
        }
        is RenderedLine.Header -> {
            val style = when (line.level) {
                1 -> MaterialTheme.typography.titleLarge.copy(fontWeight = FontWeight.Bold, color = Color.White)
                2 -> MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.Bold, color = Color.White)
                else -> MaterialTheme.typography.titleSmall.copy(fontWeight = FontWeight.Bold, color = Color.White)
            }
            val padTop = if (line.level == 1) 10.dp else if (line.level == 2) 6.dp else 4.dp
            ClickableMarkdownLine(
                annotatedText = line.annotatedText,
                style = style,
                modifier = Modifier.padding(top = padTop, bottom = 2.dp)
            )
        }
        is RenderedLine.Bullet -> {
            val isHeading = line.isSectionHeader
            val topPad = if (isHeading) 6.dp else 2.dp
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(start = (line.indentLevel * 14 + 2).dp, top = topPad, bottom = 2.dp),
                verticalAlignment = Alignment.Top
            ) {
                Text(
                    text = line.prefix,
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = if (isHeading) FontWeight.Bold else FontWeight.SemiBold,
                    color = if (isHeading) Color.White else Color(0xFFC7C7CC),
                    modifier = Modifier.padding(end = 8.dp)
                )
                ClickableMarkdownLine(
                    annotatedText = line.annotatedText,
                    style = MaterialTheme.typography.bodyMedium.copy(
                        color = if (isHeading) Color.White else Color(0xFFECECEC),
                        lineHeight = 22.sp,
                        fontWeight = if (isHeading) FontWeight.SemiBold else FontWeight.Normal
                    ),
                    modifier = Modifier.weight(1f)
                )
            }
        }
        is RenderedLine.Paragraph -> {
            ClickableMarkdownLine(
                annotatedText = line.annotatedText,
                style = MaterialTheme.typography.bodyMedium.copy(
                    color = Color(0xFFECECEC),
                    lineHeight = 22.sp
                ),
                modifier = Modifier.padding(vertical = 1.dp)
            )
        }
    }
}

@Composable
private fun TextBlockView(
    content: String,
    textColor: Color,
    linkColor: Color,
    codeBgColor: Color,
    searchResults: List<SearchResult> = emptyList()
) {
    val cacheKey = remember(content, textColor, linkColor, codeBgColor, searchResults.size) {
        "v3|$content|${textColor.value}|${linkColor.value}|${codeBgColor.value}|${searchResults.size}"
    }
    val parsedLines = remember(cacheKey) {
        val cached = renderedLineCache.get(cacheKey)
        if (cached != null) {
            cached
        } else {
            val lines = parseMarkdownLines(content, textColor, linkColor, codeBgColor, searchResults)
            renderedLineCache.put(cacheKey, lines)
            lines
        }
    }

    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        for (line in parsedLines) {
            RenderMarkdownLine(line)
        }
    }
}

/**
 * Minimalist ChatGPT-style copy button that provides immediate visual feedback
 * with an emerald checkmark transition and haptic feedback.
 */
@Composable
fun CopyIconButton(
    textToCopy: String,
    modifier: Modifier = Modifier,
    showLabel: Boolean = false,
    toastMessage: String = "Copied to clipboard"
) {
    val context = LocalContext.current
    val clipboard = LocalClipboardManager.current
    val haptic = LocalHapticFeedback.current
    var isCopied by remember { mutableStateOf(false) }

    LaunchedEffect(isCopied) {
        if (isCopied) {
            delay(1500)
            isCopied = false
        }
    }

    val greyColor = Color(0xFF9E9E9E)
    val successColor = Color(0xFF10A37F)

    Row(
        modifier = modifier
            .clip(RoundedCornerShape(6.dp))
            .clickable {
                haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                clipboard.setText(AnnotatedString(textToCopy))
                isCopied = true
                Toast.makeText(context, toastMessage, Toast.LENGTH_SHORT).show()
            }
            .padding(horizontal = 6.dp, vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(4.dp)
    ) {
        AnimatedContent(
            targetState = isCopied,
            transitionSpec = {
                fadeIn(animationSpec = tween(150)) togetherWith fadeOut(animationSpec = tween(150))
            },
            label = "CopyIconAnimation"
        ) { copied ->
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(4.dp)
            ) {
                Icon(
                    imageVector = if (copied) Icons.Default.Check else Icons.Default.ContentCopy,
                    contentDescription = if (copied) "Copied" else "Copy code",
                    tint = if (copied) successColor else greyColor,
                    modifier = Modifier.size(14.dp)
                )
                if (showLabel) {
                    Text(
                        text = if (copied) "Copied!" else "Copy code",
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Medium,
                        color = if (copied) successColor else greyColor
                    )
                }
            }
        }
    }
}

fun isMarkdownOrTextBlock(language: String, code: String): Boolean {
    val clean = language.trim().lowercase()
    if (clean in setOf("markdown", "md", "text", "txt", "plaintext", "prompt", "system", "output", "raw", "instruction")) {
        return true
    }
    if (clean.isEmpty() || clean == "code") {
        val trimmed = code.trim()
        val looksLikeMarkdown = trimmed.startsWith("#") ||
                trimmed.startsWith("•") ||
                trimmed.startsWith("* ") ||
                trimmed.startsWith("- ") ||
                trimmed.contains("\n1. ") ||
                trimmed.contains("\n• ") ||
                trimmed.contains("\n- ") ||
                trimmed.contains("\n* ") ||
                trimmed.contains("**") ||
                (trimmed.contains(". ") && !trimmed.contains(";") && !trimmed.contains("{") && !trimmed.contains("def ") && !trimmed.contains("fun ") && !trimmed.contains("class "))
        return looksLikeMarkdown
    }
    return false
}

/**
 * ChatGPT-style Code / Markdown Block.
 * - For markdown/text: seamless dark container (0xFF212121), copy button on top-right, clean typography.
 * - For programming code: seamless dark container (0xFF212121), language badge on left, copy button on right, syntax highlighting.
 */
@Composable
fun CodeBlockView(
    language: String,
    code: String,
    modifier: Modifier = Modifier
) {
    val isMarkdownOrText = remember(language, code) { isMarkdownOrTextBlock(language, code) }

    if (isMarkdownOrText) {
        MarkdownCardView(
            code = code,
            modifier = modifier
        )
    } else {
        ProgrammingCodeBlockView(
            language = language,
            code = code,
            modifier = modifier
        )
    }
}

@Composable
private fun MarkdownCardView(
    code: String,
    modifier: Modifier = Modifier
) {
    val textColor = Color(0xFFECECEC)
    val linkColor = Color(0xFF58A6FF)
    val codeBgColor = Color(0xFF2B2B2F)

    val parsedLines = remember(code) {
        parseMarkdownLines(code, textColor, linkColor, codeBgColor)
    }

    Surface(
        shape = RoundedCornerShape(16.dp),
        color = Color(0xFF212121), // Official ChatGPT dark surface
        border = BorderStroke(1.dp, Color(0xFF2E2E30)),
        modifier = modifier
            .fillMaxWidth()
            .padding(vertical = 6.dp)
            .clip(RoundedCornerShape(16.dp))
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 14.dp)
        ) {
            if (parsedLines.isEmpty()) {
                CopyIconButton(
                    textToCopy = code,
                    modifier = Modifier.align(Alignment.TopEnd)
                )
            } else {
                Column(modifier = Modifier.fillMaxWidth()) {
                    // Line 0 sits in a Row with the CopyIconButton at top-right
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.Top
                    ) {
                        Box(
                            modifier = Modifier
                                .weight(1f)
                                .padding(end = 10.dp)
                        ) {
                            RenderMarkdownLine(parsedLines[0])
                        }
                        CopyIconButton(textToCopy = code)
                    }

                    // Remaining lines take full width of the card
                    if (parsedLines.size > 1) {
                        Column(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(top = 4.dp),
                            verticalArrangement = Arrangement.spacedBy(4.dp)
                        ) {
                            for (i in 1 until parsedLines.size) {
                                RenderMarkdownLine(parsedLines[i])
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun ProgrammingCodeBlockView(
    language: String,
    code: String,
    modifier: Modifier = Modifier
) {
    val scrollState = rememberScrollState()
    val displayLang = if (language.isNotBlank()) language.lowercase() else "code"

    Surface(
        shape = RoundedCornerShape(16.dp),
        color = Color(0xFF212121), // ChatGPT dark surface
        border = BorderStroke(1.dp, Color(0xFF2E2E30)),
        modifier = modifier
            .fillMaxWidth()
            .padding(vertical = 6.dp)
            .clip(RoundedCornerShape(16.dp))
    ) {
        Column(modifier = Modifier.fillMaxWidth()) {
            // Header Bar: language name on left, "Copy code" in sleek grey on right
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(Color(0xFF282828))
                    .padding(horizontal = 14.dp, vertical = 6.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = displayLang,
                    style = MaterialTheme.typography.labelMedium.copy(
                        fontFamily = FontFamily.Default,
                        fontWeight = FontWeight.Medium,
                        fontSize = 12.sp,
                        color = Color(0xFF9E9E9E)
                    )
                )

                CopyIconButton(textToCopy = code, showLabel = true)
            }

            // Subtle divider line
            HorizontalDivider(color = Color(0xFF333336), thickness = 0.8.dp)

            // Code Content
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .horizontalScroll(scrollState)
                    .padding(horizontal = 16.dp, vertical = 12.dp)
            ) {
                Text(
                    text = highlightCodeSyntax(code, language),
                    fontFamily = FontFamily.Monospace,
                    fontSize = 13.sp,
                    lineHeight = 19.sp,
                    color = Color(0xFFD4D4D4)
                )
            }
        }
    }
}

private val GREEK_MAP = listOf(
    "\\varepsilon" to "ε", "\\vartheta" to "θ", "\\varrho" to "ρ", "\\varphi" to "φ", "\\varsigma" to "ς",
    "\\alpha" to "α", "\\Alpha" to "Α",
    "\\beta" to "β", "\\Beta" to "Β",
    "\\gamma" to "γ", "\\Gamma" to "Γ",
    "\\delta" to "δ", "\\Delta" to "Δ",
    "\\epsilon" to "ε",
    "\\zeta" to "ζ",
    "\\eta" to "η",
    "\\theta" to "θ", "\\Theta" to "Θ",
    "\\iota" to "ι",
    "\\kappa" to "κ",
    "\\lambda" to "λ", "\\Lambda" to "Λ",
    "\\mu" to "μ",
    "\\nu" to "ν",
    "\\xi" to "ξ", "\\Xi" to "Ξ",
    "\\pi" to "π", "\\Pi" to "Π", "\\varpi" to "ϖ",
    "\\rho" to "ρ",
    "\\sigma" to "σ", "\\Sigma" to "Σ",
    "\\tau" to "τ",
    "\\upsilon" to "υ", "\\Upsilon" to "Υ",
    "\\phi" to "φ", "\\Phi" to "Φ",
    "\\chi" to "χ",
    "\\psi" to "ψ", "\\Psi" to "Ψ",
    "\\omega" to "ω", "\\Omega" to "Ω"
)

private val MATH_SYMBOLS_MAP = listOf(
    "\\cdot" to " · ",
    "\\times" to " × ",
    "\\div" to " ÷ ",
    "\\odot" to " ⊙ ",
    "\\otimes" to " ⊗ ",
    "\\oplus" to " ⊕ ",
    "\\ominus" to " ⊖ ",
    "\\oslash" to " ⊘ ",
    "\\circ" to " ∘ ",
    "\\bullet" to " • ",
    "\\star" to " ★ ",
    "\\ast" to " * ",
    "\\dagger" to " † ",
    "\\ddagger" to " ‡ ",
    "\\pm" to "±",
    "\\mp" to "∓",
    "\\neq" to " ≠ ", "\\ne" to " ≠ ",
    "\\leq" to " ≤ ", "\\le" to " ≤ ",
    "\\geq" to " ≥ ", "\\ge" to " ≥ ",
    "\\approx" to " ≈ ",
    "\\sim" to " ∼ ",
    "\\simeq" to " ≃ ",
    "\\equiv" to " ≡ ",
    "\\cong" to " ≅ ",
    "\\propto" to " ∝ ",
    "\\in" to " ∈ ",
    "\\notin" to " ∉ ",
    "\\subset" to " ⊂ ",
    "\\subseteq" to " ⊆ ",
    "\\supset" to " ⊃ ",
    "\\supseteq" to " ⊇ ",
    "\\cup" to " ∪ ",
    "\\cap" to " ∩ ",
    "\\rightarrow" to " → ", "\\to" to " → ",
    "\\leftarrow" to " ← ", "\\gets" to " ← ",
    "\\Rightarrow" to " ⇒ ", "\\Leftarrow" to " ⇐ ",
    "\\leftrightarrow" to " ↔ ", "\\Leftrightarrow" to " ⇔ ",
    "\\mapsto" to " ↦ ",
    "\\infty" to "∞",
    "\\partial" to "∂",
    "\\nabla" to "∇",
    "\\forall" to "∀",
    "\\exists" to "∃", "\\nexists" to "∄",
    "\\sum" to "∑",
    "\\prod" to "∏",
    "\\int" to "∫", "\\oint" to "∮",
    "\\parallel" to " ‖ ",
    "\\|" to " ‖ ",
    "\\sqrt" to "√",
    "\\dots" to "…", "\\cdots" to "…", "\\ldots" to "…", "\\vdots" to "⋮", "\\ddots" to "⋱",
    "\\quad" to " ", "\\qquad" to "  ", "\\," to " ", "\\;" to " ", "\\!" to ""
)

private val MATH_FUNCTIONS_MAP = listOf(
    "\\log" to "log",
    "\\ln" to "ln",
    "\\exp" to "exp",
    "\\sin" to "sin",
    "\\cos" to "cos",
    "\\tan" to "tan",
    "\\cot" to "cot",
    "\\sec" to "sec",
    "\\csc" to "csc",
    "\\arcsin" to "arcsin",
    "\\arccos" to "arccos",
    "\\arctan" to "arctan",
    "\\sinh" to "sinh",
    "\\cosh" to "cosh",
    "\\tanh" to "tanh",
    "\\min" to "min",
    "\\max" to "max",
    "\\arg" to "arg",
    "\\det" to "det",
    "\\dim" to "dim",
    "\\lim" to "lim",
    "\\sup" to "sup",
    "\\inf" to "inf",
    "\\gcd" to "gcd",
    "\\deg" to "deg",
    "\\Pr" to "P",
    "\\ker" to "ker",
    "\\hom" to "hom"
)

private val CAL_MAP = mapOf(
    'A' to "𝒜", 'B' to "ℬ", 'C' to "𝒞", 'D' to "𝒟", 'E' to "ℰ",
    'F' to "ℱ", 'G' to "𝒢", 'H' to "ℋ", 'I' to "ℐ", 'J' to "𝒥",
    'K' to "𝒦", 'L' to "ℒ", 'M' to "ℳ", 'N' to "𝓝", 'O' to "𝒪",
    'P' to "𝒫", 'Q' to "𝒬", 'R' to "ℛ", 'S' to "𝒮", 'T' to "𝒯",
    'U' to "𝒰", 'V' to "𝒱", 'W' to "𝒲", 'X' to "𝒳", 'Y' to "𝒴", 'Z' to "𝒵"
)

private val BB_MAP = mapOf(
    'R' to "ℝ", 'C' to "ℂ", 'N' to "ℕ", 'Z' to "ℤ", 'Q' to "ℚ",
    'E' to "𝔼", 'P' to "ℙ", 'V' to "𝕍"
)

private val SUP_MAP = mapOf(
    '0' to '⁰', '1' to '¹', '2' to '²', '3' to '³', '4' to '⁴',
    '5' to '⁵', '6' to '⁶', '7' to '⁷', '8' to '⁸', '9' to '⁹',
    '+' to '⁺', '-' to '⁻', '=' to '⁼', '(' to '⁽', ')' to '⁾',
    'n' to 'ⁿ', 'i' to 'ⁱ', 'T' to 'ᵀ', 'x' to 'ˣ'
)

private val SUB_MAP = mapOf(
    '0' to '₀', '1' to '₁', '2' to '₂', '3' to '₃', '4' to '₄',
    '5' to '₅', '6' to '₆', '7' to '₇', '8' to '₈', '9' to '₉',
    '+' to '₊', '-' to '₋', '=' to '₌', '(' to '₍', ')' to '₎',
    'a' to 'ₐ', 'e' to 'ₑ', 'h' to 'ₕ', 'i' to 'ᵢ', 'j' to 'ⱼ',
    'k' to 'ₖ', 'l' to 'ₗ', 'm' to 'ₘ', 'n' to 'ₙ', 'o' to 'ₒ',
    'p' to 'ₚ', 'r' to 'ᵣ', 's' to 'ₛ', 't' to 'ₜ', 'u' to 'ᵤ',
    'v' to 'ᵥ', 'x' to 'ₓ'
)

private val REGEX_MATH_TEXT_WRAPPERS = Regex("""\\(?:text|mathrm|mathbf|boldsymbol|operatorname|mathit|mathsf|mathtt|mathscr|frak)\{([^}]+)\}""")
private val REGEX_MATH_CAL = Regex("""\\mathcal\{([A-Za-z])\}|\\mathcal\s+([A-Za-z])""")
private val REGEX_MATH_BB = Regex("""\\mathbb\{([A-Za-z])\}|\\mathbb\s+([A-Za-z])""")
private val REGEX_MATH_FRAC = Regex("""\\frac\{([^}]+)\}\{([^}]+)\}""")
private val REGEX_MATH_SQRT = Regex("""\\sqrt\{([^}]+)\}""")
private val REGEX_MATH_ACCENTS = Regex("""\\(?:vec|hat|bar|tilde)\{([^}]+)\}""")
private val REGEX_PAREN_BAR = Regex("""\(([^()|]+)\|([^()|]+)\)""")

/**
 * Transforms raw LaTeX math equations and symbols into clean, readable Unicode math representation (ChatGPT style).
 * Supports Greek letters (\mu -> μ, \sigma -> σ), functions (\log -> log), circled ops (\odot -> ⊙),
 * calligraphic (\mathcal{N} -> 𝓝), operators (\cdot -> ·, \sim -> ∼), \text{...}, superscripts,
 * subscripts, and removes raw bounding delimiters ($...$, $$...$$, \[...\], \(...\)).
 */
fun formatLatexMath(input: String): String {
    if (!input.contains('$') && !input.contains('\\') && !input.contains('^') && !input.contains('_')) return input

    var s = input

    // 1. Strip display math environments: \begin{equation}, \end{align*}, etc.
    s = s.replace(Regex("""\\(?:begin|end)\{[a-zA-Z*]+\}"""), "")

    // 2. Delimiters: \[ ... \] and \( ... \)
    s = s.replace("\\[", "")
        .replace("\\]", "")
        .replace("\\(", "(")
        .replace("\\)", ")")

    // 3. Multi-line display math $$ ... $$ and inline $ ... $
    s = s.replace(Regex("""\$\$([\s\S]*?)\$\$""")) { match ->
        match.groupValues[1].trim()
    }
    s = s.replace(Regex("""\$([^$\n]+)\$""")) { match ->
        match.groupValues[1].trim()
    }

    // 4. Calligraphic \mathcal{N} -> 𝓝 and Blackboard \mathbb{R} -> ℝ
    s = s.replace(REGEX_MATH_CAL) { match ->
        val ch = (match.groupValues[1].ifEmpty { match.groupValues[2] }).firstOrNull() ?: 'N'
        CAL_MAP[ch] ?: ch.toString()
    }
    s = s.replace(REGEX_MATH_BB) { match ->
        val ch = (match.groupValues[1].ifEmpty { match.groupValues[2] }).firstOrNull() ?: 'R'
        BB_MAP[ch] ?: ch.toString()
    }

    // 5. Text wrappers: \text{KL} -> KL, \mathrm{...} -> ..., etc.
    s = s.replace(REGEX_MATH_TEXT_WRAPPERS, "$1")

    // 6. Vector / Hat accents: \vec{x} -> x, \hat{x} -> x
    s = s.replace(REGEX_MATH_ACCENTS, "$1")

    // 7. Fractions: \frac{a}{b} -> (a / b)
    s = s.replace(REGEX_MATH_FRAC, "($1 / $2)")

    // 8. Square root: \sqrt{x} -> √(x)
    s = s.replace(REGEX_MATH_SQRT, "√($1)")

    // 9. Standard Math Functions: \log -> log, \ln -> ln, \exp -> exp, etc.
    for ((latexFn, cleanFn) in MATH_FUNCTIONS_MAP) {
        val pattern = Regex("""\""" + latexFn + """(?=[^a-zA-Z]|$)""")
        s = s.replace(pattern, cleanFn)
    }

    // 10. Greek letters replacement
    for ((latex, unicode) in GREEK_MAP) {
        s = s.replace(latex, unicode)
    }

    // 11. Math symbols replacement (\cdot -> ·, \odot -> ⊙, etc.)
    for ((latex, unicode) in MATH_SYMBOLS_MAP) {
        s = s.replace(latex, unicode)
    }

    // 12. Brackets: \left(, \right), etc.
    s = s.replace("\\left(", "(")
        .replace("\\right)", ")")
        .replace("\\left[", "[")
        .replace("\\right]", "]")
        .replace("\\left\\{", "{")
        .replace("\\right\\}", "}")
        .replace("\\left|", "|")
        .replace("\\right|", "|")
        .replace("\\left.", "")
        .replace("\\right.", "")
        .replace("\\{", "{")
        .replace("\\}", "}")

    // 13. Superscripts: ^{2} -> ², ^2 -> ², ^{T} -> ᵀ, etc.
    s = s.replace(Regex("""\^\{([0-9+\-=()niTx]+)\}""")) { match ->
        match.groupValues[1].map { SUP_MAP[it] ?: it }.joinToString("")
    }
    s = s.replace(Regex("""\^([0-9niTx])(?![a-zA-Z0-9])""")) { match ->
        SUP_MAP[match.groupValues[1][0]]?.toString() ?: match.value
    }
    s = s.replace("^{*}", "*").replace("^*", "*").replace("^{-1}", "⁻¹")

    // 14. Subscripts: _{0} -> ₀, _{i} -> ᵢ, etc.
    s = s.replace(Regex("""_\{([0-9+\-=()aehijklmnoprstuvx]+)\}""")) { match ->
        match.groupValues[1].map { SUB_MAP[it] ?: it }.joinToString("")
    }
    s = s.replace(Regex("""_([0-9ijknxt])(?![a-zA-Z0-9])""")) { match ->
        SUB_MAP[match.groupValues[1][0]]?.toString() ?: match.value
    }
    s = s.replace("_{KL}", "_KL").replace("_{total}", "_total")

    // 15. Conditionals (z|x) -> (z | x)
    s = s.replace(REGEX_PAREN_BAR, "($1 | $2)")
    s = s.replace("||", " ‖ ")

    // 16. Clean duplicate spaces
    s = s.replace(Regex("""[ \t]{2,}"""), " ")

    return s
}

/**
 * Splits a table line on '|' while correctly preserving pipes inside math formulas (e.g. $Q(z|x)$) or backticks.
 */
fun splitTableRow(line: String): List<String> {
    val cells = mutableListOf<String>()
    val current = StringBuilder()
    var inMath = false
    var inCode = false
    var i = 0
    val len = line.length

    while (i < len) {
        val c = line[i]
        if (c == '`') {
            inCode = !inCode
            current.append(c)
        } else if (c == '$' && !inCode) {
            inMath = !inMath
            current.append(c)
        } else if (c == '|' && !inMath && !inCode) {
            cells.add(current.toString().trim())
            current.clear()
        } else {
            current.append(c)
        }
        i++
    }
    cells.add(current.toString().trim())
    return cells
}

/**
 * Cleans table cells, stripping surrounding quotes, formatting LaTeX math cleanly,
 * and balancing any stray asterisks so markdown text styles properly as bold/italic with zero raw stars rendered.
 */
fun cleanTableCell(raw: String): String {
    var s = raw.replace("\\_", "_").trim()
    // Strip surrounding quotes if any
    if (s.length >= 2 && ((s.startsWith("\"") && s.endsWith("\"")) || (s.startsWith("'") && s.endsWith("'")))) {
        s = s.substring(1, s.length - 1).trim()
    }
    // Clean and beautify any LaTeX / mathematical notation
    s = formatLatexMath(s)
    // Balance trailing ** if missing leading **
    if (s.endsWith("**") && !s.startsWith("**")) {
        s = "**$s"
    } else if (s.startsWith("**") && !s.endsWith("**")) {
        s = "$s**"
    }
    // Balance single * if missing counterpart
    val starsWithoutDouble = s.replace("**", "")
    if (starsWithoutDouble.count { it == '*' } % 2 != 0) {
        if (s.endsWith("*") && !s.endsWith("**")) {
            s = "*$s"
        } else if (s.startsWith("*") && !s.startsWith("**")) {
            s = "$s*"
        }
    }
    return s
}

/**
 * ChatGPT-style clean, open, borderless Data Table View.
 * Renders directly on the AMOLED pure dark background with crisp typography,
 * subtle horizontal dividers, and inline markdown formatting (bold, italic, links).
 */
@Composable
fun MarkdownTableView(
    headers: List<String>,
    rows: List<List<String>>,
    modifier: Modifier = Modifier
) {
    val scrollState = rememberScrollState()
    val isCompact = headers.size <= 3

    Box(
        modifier = modifier
            .fillMaxWidth()
            .padding(vertical = 8.dp)
    ) {
        val tableContent: @Composable () -> Unit = {
            Column(modifier = if (isCompact) Modifier.fillMaxWidth() else Modifier) {
                // Header Row
                Row(
                    modifier = if (isCompact) Modifier.fillMaxWidth().padding(vertical = 10.dp)
                               else Modifier.padding(vertical = 10.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    headers.forEachIndexed { colIndex, header ->
                        val cellModifier = if (isCompact) {
                            Modifier.weight(1f).padding(end = if (colIndex < headers.size - 1) 12.dp else 0.dp)
                        } else {
                            Modifier.widthIn(min = 120.dp, max = 240.dp).padding(end = 16.dp)
                        }
                        Box(modifier = cellModifier) {
                            val cleanHeader = cleanTableCell(header)
                            Text(
                                text = buildInlineMarkdown(cleanHeader, defaultColor = Color.White),
                                style = MaterialTheme.typography.bodyMedium.copy(
                                    fontSize = 14.sp,
                                    lineHeight = 20.sp,
                                    fontWeight = FontWeight.SemiBold
                                ),
                                color = Color.White
                            )
                        }
                    }
                }

                // Header Divider line (matching ChatGPT: clean subtle separator under headers)
                HorizontalDivider(color = Color(0xFF2C2C30), thickness = 0.8.dp)

                // Data Rows
                rows.forEachIndexed { rowIndex, row ->
                    Row(
                        modifier = if (isCompact) Modifier.fillMaxWidth().padding(vertical = 10.dp)
                                   else Modifier.padding(vertical = 10.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        headers.indices.forEach { colIndex ->
                            val rawCell = row.getOrNull(colIndex) ?: ""
                            val cleanCell = cleanTableCell(rawCell)
                            val cellModifier = if (isCompact) {
                                Modifier.weight(1f).padding(end = if (colIndex < headers.size - 1) 12.dp else 0.dp)
                            } else {
                                Modifier.widthIn(min = 120.dp, max = 240.dp).padding(end = 16.dp)
                            }
                            Box(modifier = cellModifier) {
                                Text(
                                    text = buildInlineMarkdown(cleanCell, defaultColor = Color(0xFFECECEC)),
                                    style = MaterialTheme.typography.bodyMedium.copy(
                                        fontSize = 13.5.sp,
                                        lineHeight = 19.5.sp
                                    ),
                                    color = Color(0xFFECECEC)
                                )
                            }
                        }
                    }

                    // Divider between rows (matching ChatGPT: ultra-thin subtle line)
                    HorizontalDivider(color = Color(0xFF1E1E22), thickness = 0.5.dp)
                }
            }
        }

        if (isCompact) {
            tableContent()
        } else {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .horizontalScroll(scrollState)
            ) {
                tableContent()
            }
        }
    }
}

/**
 * Parses raw text into alternating Code blocks, Tables, and regular Markdown blocks.
 */
fun parseMarkdownBlocks(input: String): List<MarkdownBlock> {
    if (input.isBlank()) return emptyList()
    val cached = markdownBlockCache.get(input)
    if (cached != null) return cached

    // Fast-path: 90%+ of text messages have no code blocks and no tables
    if (!input.contains("```") && !input.contains('|')) {
        val result = listOf(MarkdownBlock.Text(input))
        markdownBlockCache.put(input, result)
        return result
    }

    val blocks = mutableListOf<MarkdownBlock>()
    var currentIndex = 0

    for (match in REGEX_CODE_BLOCK.findAll(input)) {
        if (match.range.first > currentIndex) {
            val textPart = input.substring(currentIndex, match.range.first)
            if (textPart.isNotBlank()) {
                blocks.addAll(extractTablesAndText(textPart))
            }
        }
        val lang = match.groupValues[1].trim()
        val code = match.groupValues[2].trimEnd()
        blocks.add(MarkdownBlock.Code(language = lang, code = code))
        currentIndex = match.range.last + 1
    }

    if (currentIndex < input.length) {
        val remaining = input.substring(currentIndex)
        val unclosedMatch = REGEX_UNCLOSED_CODE.find(remaining)
        if (unclosedMatch != null) {
            val beforeUnclosed = remaining.substring(0, unclosedMatch.range.first)
            if (beforeUnclosed.isNotBlank()) {
                blocks.addAll(extractTablesAndText(beforeUnclosed))
            }
            val lang = unclosedMatch.groupValues[1].trim()
            val code = unclosedMatch.groupValues[2].trimEnd()
            blocks.add(MarkdownBlock.Code(language = lang, code = code))
        } else {
            if (remaining.isNotBlank()) {
                blocks.addAll(extractTablesAndText(remaining))
            }
        }
    }

    val result = if (blocks.isEmpty() && input.isNotBlank()) listOf(MarkdownBlock.Text(input)) else blocks
    markdownBlockCache.put(input, result)
    return result
}

/**
 * Extracts Markdown tables from text and returns a sequence of Text and Table blocks.
 */
fun extractTablesAndText(text: String): List<MarkdownBlock> {
    if (!text.contains('|')) {
        return if (text.isNotBlank()) listOf(MarkdownBlock.Text(text)) else emptyList()
    }

    val results = mutableListOf<MarkdownBlock>()
    var lastIdx = 0

    for (match in REGEX_TABLE.findAll(text)) {
        val start = match.range.first
        val end = match.range.last + 1
        if (start > lastIdx) {
            val prefix = text.substring(lastIdx, start)
            if (prefix.isNotBlank()) {
                results.add(MarkdownBlock.Text(prefix))
            }
        }
        val tableStr = match.value
        val parsedTable = parseMarkdownTable(tableStr)
        if (parsedTable != null) {
            results.add(parsedTable)
        } else {
            results.add(MarkdownBlock.Text(tableStr))
        }
        lastIdx = end
    }

    if (lastIdx < text.length) {
        val suffix = text.substring(lastIdx)
        if (suffix.isNotBlank()) {
            results.add(MarkdownBlock.Text(suffix))
        }
    }

    return if (results.isEmpty() && text.isNotBlank()) listOf(MarkdownBlock.Text(text)) else results
}

/**
 * Parses a raw Markdown table string into a MarkdownBlock.Table data class.
 */
fun parseMarkdownTable(raw: String): MarkdownBlock.Table? {
    val lines = raw.trim().lines().map { it.trim() }.filter { it.isNotEmpty() }
    if (lines.size < 2) return null
    val headerLine = lines[0]
    val separatorLine = lines[1]
    if (!headerLine.startsWith("|") || !separatorLine.startsWith("|")) return null

    val rawHeaders = splitTableRow(headerLine)
    val headers = if (rawHeaders.size > 2 && rawHeaders.first().isEmpty() && rawHeaders.last().isEmpty()) {
        rawHeaders.subList(1, rawHeaders.size - 1)
    } else {
        rawHeaders.filter { it.isNotEmpty() }
    }
    if (headers.isEmpty()) return null

    val rows = mutableListOf<List<String>>()
    for (i in 2 until lines.size) {
        val line = lines[i]
        if (line.startsWith("|")) {
            val rawCells = splitTableRow(line)
            val cells = if (rawCells.size > 2 && rawCells.first().isEmpty() && rawCells.last().isEmpty()) {
                rawCells.subList(1, rawCells.size - 1)
            } else {
                rawCells.filter { it.isNotEmpty() }
            }
            if (cells.isNotEmpty()) {
                val padded = cells.toMutableList()
                while (padded.size < headers.size) padded.add("")
                rows.add(padded.take(headers.size))
            }
        }
    }
    return if (rows.isNotEmpty()) MarkdownBlock.Table(headers, rows) else null
}

/**
 * Tokenizes code into syntax-highlighted AnnotatedString.
 */
fun highlightCodeSyntax(code: String, language: String): AnnotatedString {
    val keywords = setOf(
        "fun", "val", "var", "def", "class", "interface", "object", "import", "package",
        "return", "if", "else", "while", "for", "in", "when", "case", "break", "continue",
        "try", "catch", "finally", "throw", "new", "public", "private", "protected",
        "override", "true", "false", "null", "None", "async", "await", "yield", "lambda",
        "const", "let", "function", "export", "from", "extends", "implements", "this",
        "super", "switch", "default", "struct", "enum", "type", "void", "int", "float",
        "double", "boolean", "string", "String", "bool", "select", "from", "where", "insert"
    )

    val keywordColor = Color(0xFFC792EA) // Vivid purple
    val stringColor = Color(0xFFC3E88D)  // Light green
    val commentColor = Color(0xFF676E95) // Muted italic slate
    val numberColor = Color(0xFFF78C6C)  // Light orange
    val defaultColor = Color(0xFFD4D4D4) // Clean white/light gray

    return buildAnnotatedString {
        val lines = code.lines()
        for ((lineIdx, line) in lines.withIndex()) {
            val trimmed = line.trimStart()
            if (trimmed.startsWith("//") || trimmed.startsWith("#")) {
                withStyle(SpanStyle(color = commentColor, fontStyle = FontStyle.Italic)) {
                    append(line)
                }
            } else {
                var i = 0
                val len = line.length
                while (i < len) {
                    val ch = line[i]

                    // String literal
                    if (ch == '"' || ch == '\'') {
                        val quote = ch
                        var end = i + 1
                        while (end < len && line[end] != quote) {
                            if (line[end] == '\\' && end + 1 < len) end++
                            end++
                        }
                        if (end < len) end++ // include closing quote
                        withStyle(SpanStyle(color = stringColor)) {
                            append(line.substring(i, end))
                        }
                        i = end
                        continue
                    }

                    // Word / Identifier
                    if (ch.isLetter() || ch == '_') {
                        var end = i + 1
                        while (end < len && (line[end].isLetterOrDigit() || line[end] == '_')) {
                            end++
                        }
                        val word = line.substring(i, end)
                        if (word in keywords) {
                            withStyle(SpanStyle(color = keywordColor, fontWeight = FontWeight.Bold)) {
                                append(word)
                            }
                        } else {
                            withStyle(SpanStyle(color = defaultColor)) {
                                append(word)
                            }
                        }
                        i = end
                        continue
                    }

                    // Number
                    if (ch.isDigit()) {
                        var end = i + 1
                        while (end < len && (line[end].isLetterOrDigit() || line[end] == '.')) {
                            end++
                        }
                        withStyle(SpanStyle(color = numberColor)) {
                            append(line.substring(i, end))
                        }
                        i = end
                        continue
                    }

                    // Other characters / punctuation
                    withStyle(SpanStyle(color = defaultColor)) {
                        append(ch)
                    }
                    i++
                }
            }

            if (lineIdx < lines.size - 1) {
                append("\n")
            }
        }
    }
}

/**
 * Clickable markdown text line that intercepts tapped URLs and opens them via LocalUriHandler.
 */
@Composable
fun ClickableMarkdownLine(
    annotatedText: AnnotatedString,
    style: TextStyle,
    modifier: Modifier = Modifier
) {
    val uriHandler = LocalUriHandler.current

    ClickableText(
        text = annotatedText,
        style = style,
        modifier = modifier,
        onClick = { offset ->
            annotatedText.getStringAnnotations(tag = "URL", start = offset, end = offset)
                .firstOrNull()?.let { annotation ->
                    try {
                        uriHandler.openUri(annotation.item)
                    } catch (_: Exception) {}
                }
        }
    )
}

/**
 * Resolves recognizable source brand and badge for a web search URL.
 */
fun getSourceBrand(url: String, title: String): Pair<String, String> {
    val host = try { java.net.URI(url).host?.removePrefix("www.")?.lowercase() ?: "" } catch (_: Exception) { "" }
    val isLinkedIn = host.contains("linkedin") || title.contains("linkedin", ignoreCase = true)
    val isGitHub = host.contains("github") || title.contains("github", ignoreCase = true)
    val isWikipedia = host.contains("wikipedia") || title.contains("wikipedia", ignoreCase = true)
    val isTwitter = host.contains("twitter") || host.contains("x.com")
    val isYoutube = host.contains("youtube") || host.contains("youtu.be")
    val isFacebook = host.contains("facebook") || host.contains("fb.com")
    val isInstagram = host.contains("instagram")
    val isSrm = host.contains("srm") || title.contains("srm", ignoreCase = true)

    val brand = when {
        isLinkedIn -> "LinkedIn"
        isGitHub -> "GitHub"
        isWikipedia -> "Wikipedia"
        isTwitter -> "X"
        isYoutube -> "YouTube"
        isFacebook -> "Facebook"
        isInstagram -> "Instagram"
        isSrm -> "SRM University"
        host.isNotBlank() -> host.substringBefore(".").replaceFirstChar { it.uppercase() }
        else -> "Source"
    }
    return brand to url
}

/**
 * Cleans unwanted math/LaTeX tokens and formats web search HTML/href artifacts into clean Markdown links.
 */
fun sanitizeMarkdown(input: String, searchResults: List<SearchResult> = emptyList()): String {
    var s = input
    // 1. Math/LaTeX format & beautification
    s = formatLatexMath(s)

    // 2. Strip robotic disclaimers so response sounds natural like ChatGPT
    val roboticPrefixes = listOf(
        "Based on the live web search results,",
        "Based on the live web search results",
        "Based on the web search results,",
        "Based on the web search results",
        "According to the live web search results,",
        "According to the search results,",
        "According to live search results,",
        "Here are the details gathered from the search results:",
        "Here are the details gathered from the search results",
        "Here are the search results:"
    )
    for (rp in roboticPrefixes) {
        if (s.startsWith(rp, ignoreCase = true)) {
            s = s.removePrefix(rp).trimStart()
        }
    }

    // 3. Web search link sanitation: convert HTML <a> tags and raw href="..." to clean Markdown links
    if (s.contains("<a", ignoreCase = true)) {
        s = s.replace(REGEX_HTML_LINK) { match ->
            val url = match.groupValues[1]
            val text = match.groupValues[2].trim()
            if (text.isNotBlank() && !text.equals("href", true) && !text.equals("link", true) && !text.equals("url", true)) {
                "[$text]($url)"
            } else {
                val (b, u) = getSourceBrand(url, "")
                "[$b]($u)"
            }
        }
        s = s.replace(REGEX_HTML_SELF_CLOSING) { match ->
            val url = match.groupValues[1]
            val (b, u) = getSourceBrand(url, "")
            "[$b]($u)"
        }
    }
    if (s.contains("href=", ignoreCase = true)) {
        s = s.replace(REGEX_RAW_HREF) { match ->
            val url = match.groupValues[1]
            val (b, u) = getSourceBrand(url, "")
            "[$b]($u)"
        }
    }

    // 4. Map numeric citation references like [1], [2], [1, 2] to sleek clickable citation pills
    if (searchResults.isNotEmpty()) {
        val numCitationRegex = Regex("""\[([0-9]+(?:\s*,\s*[0-9]+)*)\]""")
        s = s.replace(numCitationRegex) { match ->
            val numStr = match.groupValues[1].trim()
            val indices = numStr.split(",").mapNotNull { it.trim().toIntOrNull() }
            if (indices.isEmpty()) {
                match.value
            } else {
                val validResults = indices.mapNotNull { idx -> searchResults.getOrNull(idx - 1) }
                if (validResults.isEmpty()) {
                    match.value
                } else {
                    val first = validResults[0]
                    "[$numStr](${first.url})"
                }
            }
        }

        // 5. Ground markdown links [Title](url) to real URLs from searchResults to prevent random/hallucinated domains
        val markdownLinkRegex = Regex("""\[([^\]]+)\]\((https?://[^\s)]+)\)""")
        s = s.replace(markdownLinkRegex) { match ->
            val linkText = match.groupValues[1]
            val generatedUrl = match.groupValues[2]

            val matchedResult = searchResults.firstOrNull { res ->
                val resHost = try { java.net.URI(res.url).host?.removePrefix("www.")?.lowercase() } catch (_: Exception) { null }
                val genHost = try { java.net.URI(generatedUrl).host?.removePrefix("www.")?.lowercase() } catch (_: Exception) { null }

                (genHost != null && resHost != null && (genHost.contains(resHost) || resHost.contains(genHost))) ||
                (linkText.contains("linkedin", ignoreCase = true) && res.url.contains("linkedin", ignoreCase = true)) ||
                (linkText.contains("github", ignoreCase = true) && res.url.contains("github", ignoreCase = true)) ||
                (linkText.contains("hugging", ignoreCase = true) && res.url.contains("huggingface", ignoreCase = true)) ||
                (linkText.contains("wikipedia", ignoreCase = true) && res.url.contains("wikipedia", ignoreCase = true))
            }

            if (matchedResult != null) {
                "[$linkText](${matchedResult.url})"
            } else if (searchResults.isNotEmpty()) {
                // If Gemma hallucinated a random domain, ground it to the primary verified result URL
                "[$linkText](${searchResults.first().url})"
            } else {
                match.value
            }
        }

        // 6. Ground raw URLs to matching searchResults domains so users never navigate to fake URLs
        val rawUrlRegex = Regex("""https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/[^\s\)\],<]*)?""")
        s = s.replace(rawUrlRegex) { match ->
            val rawUrl = match.value
            val matched = searchResults.firstOrNull { res ->
                val resHost = try { java.net.URI(res.url).host?.removePrefix("www.")?.lowercase() } catch (_: Exception) { null }
                val rawHost = try { java.net.URI(rawUrl).host?.removePrefix("www.")?.lowercase() } catch (_: Exception) { null }
                resHost != null && rawHost != null && (resHost.contains(rawHost) || rawHost.contains(resHost))
            }
            matched?.url ?: (if (searchResults.isNotEmpty()) searchResults.first().url else rawUrl)
        }
    }

    return s
}

/**
 * Parses inline spans: links, **bold**, *italic*, and `code` into an AnnotatedString with clickable URL annotations.
 */
fun buildInlineMarkdown(
    rawText: String,
    defaultColor: Color,
    linkColor: Color = Color(0xFF58A6FF),
    codeBgColor: Color = Color(0xFFEEEEEE)
): AnnotatedString {
    val text = formatLatexMath(rawText)
    return buildAnnotatedString {
        var i = 0
        val length = text.length

        while (i < length) {
            // 1. Markdown link: [Title](https://...)
            if (text[i] == '[') {
                val closeBracket = text.indexOf(']', i + 1)
                if (closeBracket != -1 && closeBracket + 1 < length && text[closeBracket + 1] == '(') {
                    val closeParen = text.indexOf(')', closeBracket + 2)
                    if (closeParen != -1) {
                        val rawTitle = text.substring(i + 1, closeBracket).trim()
                        val url = text.substring(closeBracket + 2, closeParen).trim()
                        if (url.startsWith("http://") || url.startsWith("https://")) {
                            val isNumericCitation = rawTitle.matches(Regex("""^\[?\d+(?:\s*,\s*\d+)*\]?$"""))

                            pushStringAnnotation(tag = "URL", annotation = url)
                            if (isNumericCitation) {
                                // Subtle, compact numeric citation pill (ChatGPT style): e.g. [1]
                                val cleanNum = rawTitle.trim('[', ']')
                                withStyle(
                                    SpanStyle(
                                        color = linkColor,
                                        fontSize = 10.5.sp,
                                        fontWeight = FontWeight.SemiBold,
                                        background = Color(0xFF222226)
                                    )
                                ) {
                                    append(" $cleanNum ")
                                }
                            } else {
                                // Clean, elegant link text with ↗ arrow (matching ChatGPT)
                                withStyle(
                                    SpanStyle(
                                        color = linkColor,
                                        fontWeight = FontWeight.Medium,
                                        textDecoration = TextDecoration.Underline
                                    )
                                ) {
                                    val displayTitle = if (rawTitle.isBlank()) "Link" else rawTitle.removeSuffix("↗").trim()
                                    append("$displayTitle ↗")
                                }
                            }
                            pop()
                            i = closeParen + 1
                            continue
                        }
                    }
                }
            }

            // 2. Raw URL: http:// or https://
            if (text.startsWith("http://", i) || text.startsWith("https://", i)) {
                var end = i
                while (end < length && !text[end].isWhitespace() && text[end] != ')' && text[end] != ']' && text[end] != '>' && text[end] != '"') {
                    end++
                }
                var url = text.substring(i, end)
                while (url.endsWith(".") || url.endsWith(",") || url.endsWith(";") || url.endsWith(":")) {
                    url = url.substring(0, url.length - 1)
                    end--
                }
                if (url.isNotBlank()) {
                    val host = try { java.net.URI(url).host?.removePrefix("www.") } catch (_: Exception) { null }
                    val displayUrl = if (!host.isNullOrBlank() && !host.equals("open link", ignoreCase = true)) "$host ↗" else "Link ↗"

                    pushStringAnnotation(tag = "URL", annotation = url)
                    withStyle(
                        SpanStyle(
                            color = linkColor,
                            textDecoration = TextDecoration.Underline,
                            fontWeight = FontWeight.SemiBold
                        )
                    ) {
                        append(displayUrl)
                    }
                    pop()
                    i = end
                    continue
                }
            }

            // 3. Inline code `...`
            if (text[i] == '`') {
                val nextTick = text.indexOf('`', i + 1)
                if (nextTick != -1) {
                    val codeContent = text.substring(i + 1, nextTick)
                    withStyle(
                        SpanStyle(
                            fontFamily = FontFamily.Monospace,
                            background = codeBgColor,
                            color = Color(0xFFE2E2E6),
                            fontSize = 13.sp
                        )
                    ) {
                        append(" $codeContent ")
                    }
                    i = nextTick + 1
                    continue
                }
            }

            // 4. Bold **...**
            if (i + 1 < length && text[i] == '*' && text[i + 1] == '*') {
                val nextStar = text.indexOf("**", i + 2)
                val boldColor = if (defaultColor == Color(0xFFECECEC) || defaultColor == Color(0xFFE0E0E0)) Color.White else defaultColor
                if (nextStar != -1) {
                    val boldContent = text.substring(i + 2, nextStar)
                    withStyle(SpanStyle(fontWeight = FontWeight.Bold, color = boldColor)) {
                        append(boldContent)
                    }
                    i = nextStar + 2
                    continue
                } else {
                    val boldContent = text.substring(i + 2)
                    if (boldContent.isNotEmpty()) {
                        withStyle(SpanStyle(fontWeight = FontWeight.Bold, color = boldColor)) {
                            append(boldContent)
                        }
                    }
                    break
                }
            }

            // 5. Italic *...*
            if (text[i] == '*' && (i == 0 || text[i - 1] != '*')) {
                val nextStar = text.indexOf('*', i + 1)
                if (nextStar != -1 && (nextStar + 1 >= length || text[nextStar + 1] != '*')) {
                    val italicContent = text.substring(i + 1, nextStar)
                    withStyle(SpanStyle(fontStyle = FontStyle.Italic)) {
                        append(italicContent)
                    }
                    i = nextStar + 1
                    continue
                } else {
                    val italicContent = text.substring(i + 1)
                    if (italicContent.isNotEmpty()) {
                        withStyle(SpanStyle(fontStyle = FontStyle.Italic)) {
                            append(italicContent)
                        }
                    }
                    break
                }
            }

            append(text[i])
            i++
        }
    }
}
