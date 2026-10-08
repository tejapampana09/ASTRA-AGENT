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
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material3.Icon
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
        MaterialTheme.colorScheme.onSurface
    }

    val linkColor = if (isUser) {
        MaterialTheme.colorScheme.primary
    } else {
        Color(0xFF58A6FF) // Crisp high-contrast link blue (ChatGPT dark mode style)
    }

    val codeBgColor = if (isUser) {
        MaterialTheme.colorScheme.primary.copy(alpha = 0.15f)
    } else {
        MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.6f)
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
    data class Bullet(val prefix: String, val annotatedText: AnnotatedString) : RenderedLine()
    data class Paragraph(val annotatedText: AnnotatedString) : RenderedLine()
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
        "$content|${textColor.value}|${linkColor.value}|${codeBgColor.value}|${searchResults.size}"
    }
    val parsedLines = remember(cacheKey) {
        val cached = renderedLineCache.get(cacheKey)
        if (cached != null) {
            cached
        } else {
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
                                annotatedText = buildInlineMarkdown(c, textColor, linkColor, codeBgColor)
                            )
                        )
                    }
                    trimmed.matches(REGEX_NUMBERED_LIST) -> {
                        val prefix = trimmed.substringBefore(". ") + "."
                        val c = trimmed.substringAfter(". ").trim()
                        result.add(
                            RenderedLine.Bullet(
                                prefix = prefix,
                                annotatedText = buildInlineMarkdown(c, textColor, linkColor, codeBgColor)
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
            renderedLineCache.put(cacheKey, result)
            result
        }
    }

    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        for (line in parsedLines) {
            when (line) {
                is RenderedLine.Blank -> {
                    Spacer(modifier = Modifier.height(10.dp))
                }
                is RenderedLine.Header -> {
                    val style = when (line.level) {
                        1 -> MaterialTheme.typography.titleLarge.copy(fontWeight = FontWeight.Bold, color = textColor)
                        2 -> MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.Bold, color = textColor)
                        else -> MaterialTheme.typography.titleSmall.copy(fontWeight = FontWeight.Bold, color = textColor)
                    }
                    val padTop = if (line.level == 1) 12.dp else if (line.level == 2) 8.dp else 6.dp
                    ClickableMarkdownLine(
                        annotatedText = line.annotatedText,
                        style = style,
                        modifier = Modifier.padding(top = padTop, bottom = 4.dp)
                    )
                }
                is RenderedLine.Bullet -> {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(start = 2.dp, top = 2.dp, bottom = 2.dp),
                        verticalAlignment = Alignment.Top
                    ) {
                        Text(
                            text = line.prefix,
                            style = MaterialTheme.typography.bodyMedium,
                            fontWeight = FontWeight.SemiBold,
                            color = textColor,
                            modifier = Modifier.padding(end = 8.dp)
                        )
                        ClickableMarkdownLine(
                            annotatedText = line.annotatedText,
                            style = MaterialTheme.typography.bodyMedium.copy(color = textColor, lineHeight = 24.sp),
                            modifier = Modifier.weight(1f)
                        )
                    }
                }
                is RenderedLine.Paragraph -> {
                    ClickableMarkdownLine(
                        annotatedText = line.annotatedText,
                        style = MaterialTheme.typography.bodyMedium.copy(color = textColor, lineHeight = 24.sp),
                        modifier = Modifier.padding(vertical = 2.dp)
                    )
                }
            }
        }
    }
}

/**
 * ChatGPT-style Code Block with header, language badge, copy button and syntax highlighting.
 */
@Composable
fun CodeBlockView(
    language: String,
    code: String,
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current
    val clipboard = LocalClipboardManager.current
    val haptic = LocalHapticFeedback.current
    val scrollState = rememberScrollState()

    val displayLang = if (language.isNotBlank()) language.lowercase() else "code"

    Surface(
        shape = RoundedCornerShape(10.dp),
        color = Color(0xFF1E1E24), // Sleek VS Code / Dracula dark surface
        border = BorderStroke(1.dp, Color(0xFF33353E)),
        modifier = modifier
            .fillMaxWidth()
            .padding(vertical = 6.dp)
            .clip(RoundedCornerShape(10.dp))
    ) {
        Column(modifier = Modifier.fillMaxWidth()) {
            // Header Bar (ChatGPT style: lowercase lang on left, copy button with icon on right)
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(Color(0xFF282A36))
                    .padding(horizontal = 14.dp, vertical = 8.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = displayLang,
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.Medium,
                    color = Color(0xFFA0A6B8)
                )

                Surface(
                    shape = RoundedCornerShape(6.dp),
                    color = Color.Transparent,
                    modifier = Modifier.clickable {
                        haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                        clipboard.setText(AnnotatedString(code))
                        Toast.makeText(context, "Code copied", Toast.LENGTH_SHORT).show()
                    }
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 6.dp, vertical = 3.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            imageVector = Icons.Default.ContentCopy,
                            contentDescription = "Copy code",
                            tint = Color(0xFFD1D5DB),
                            modifier = Modifier.size(13.dp)
                        )
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(
                            text = "Copy code",
                            style = MaterialTheme.typography.labelSmall,
                            color = Color(0xFFD1D5DB)
                        )
                    }
                }
            }

            // Code Content
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .horizontalScroll(scrollState)
                    .padding(horizontal = 14.dp, vertical = 12.dp)
            ) {
                Text(
                    text = highlightCodeSyntax(code, language),
                    fontFamily = FontFamily.Monospace,
                    fontSize = 13.sp,
                    lineHeight = 18.sp
                )
            }
        }
    }
}

private val GREEK_MAP = listOf(
    "\\alpha" to "α", "\\Alpha" to "Α",
    "\\beta" to "β", "\\Beta" to "Β",
    "\\gamma" to "γ", "\\Gamma" to "Γ",
    "\\delta" to "δ", "\\Delta" to "Δ",
    "\\epsilon" to "ε", "\\varepsilon" to "ε",
    "\\zeta" to "ζ",
    "\\eta" to "η",
    "\\theta" to "θ", "\\Theta" to "Θ", "\\vartheta" to "θ",
    "\\iota" to "ι",
    "\\kappa" to "κ",
    "\\lambda" to "λ", "\\Lambda" to "Λ",
    "\\mu" to "μ",
    "\\nu" to "ν",
    "\\xi" to "ξ", "\\Xi" to "Ξ",
    "\\pi" to "π", "\\Pi" to "Π",
    "\\rho" to "ρ", "\\varrho" to "ρ",
    "\\sigma" to "σ", "\\Sigma" to "Σ",
    "\\tau" to "τ",
    "\\upsilon" to "υ", "\\Upsilon" to "Υ",
    "\\phi" to "φ", "\\Phi" to "Φ", "\\varphi" to "φ",
    "\\chi" to "χ",
    "\\psi" to "ψ", "\\Psi" to "Ψ",
    "\\omega" to "ω", "\\Omega" to "Ω"
)

private val MATH_SYMBOLS_MAP = listOf(
    "\\cdot" to " · ",
    "\\times" to " × ",
    "\\div" to " ÷ ",
    "\\pm" to "±",
    "\\mp" to "∓",
    "\\neq" to " ≠ ", "\\ne" to " ≠ ",
    "\\leq" to " ≤ ", "\\le" to " ≤ ",
    "\\geq" to " ≥ ", "\\ge" to " ≥ ",
    "\\approx" to " ≈ ",
    "\\sim" to " ∼ ",
    "\\simeq" to " ≃ ",
    "\\equiv" to " ≡ ",
    "\\propto" to " ∝ ",
    "\\in" to " ∈ ",
    "\\notin" to " ∉ ",
    "\\subset" to " ⊂ ",
    "\\subseteq" to " ⊆ ",
    "\\cup" to " ∪ ",
    "\\cap" to " ∩ ",
    "\\rightarrow" to " → ", "\\to" to " → ",
    "\\leftarrow" to " ← ",
    "\\Rightarrow" to " ⇒ ", "\\Leftarrow" to " ⇐ ",
    "\\leftrightarrow" to " ↔ ",
    "\\infty" to "∞",
    "\\partial" to "∂",
    "\\nabla" to "∇",
    "\\forall" to "∀",
    "\\exists" to "∃",
    "\\sum" to "∑",
    "\\prod" to "∏",
    "\\int" to "∫",
    "\\parallel" to " ‖ ",
    "\\|" to " ‖ ",
    "\\sqrt" to "√",
    "\\dots" to "…", "\\cdots" to "…", "\\ldots" to "…",
    "\\quad" to " ", "\\qquad" to "  ", "\\," to " ", "\\;" to " "
)

private val REGEX_MATH_TEXT_WRAPPERS = Regex("""\\(?:text|mathrm|mathbf|boldsymbol|operatorname)\{([^}]+)\}""")
private val REGEX_MATH_FRAC = Regex("""\\frac\{([^}]+)\}\{([^}]+)\}""")
private val REGEX_MATH_SQRT = Regex("""\\sqrt\{([^}]+)\}""")
private val REGEX_PAREN_BAR = Regex("""\(([^()|]+)\|([^()|]+)\)""")

/**
 * Transforms raw LaTeX math equations and symbols into clean, readable Unicode math representation (ChatGPT style).
 * Supports Greek letters (\mu -> μ, \sigma -> σ), operators (\cdot -> ·, \sim -> ∼), \text{...}, superscripts,
 * subscripts, and removes raw bounding dollar signs ($...$ and $$...$$).
 */
fun formatLatexMath(input: String): String {
    if (!input.contains('$') && !input.contains('\\')) return input

    var s = input

    // 1. Text wrappers: \text{KL} -> KL, \mathrm{...} -> ..., etc.
    s = s.replace(REGEX_MATH_TEXT_WRAPPERS, "$1")

    // 2. Fractions: \frac{a}{b} -> (a / b)
    s = s.replace(REGEX_MATH_FRAC, "($1 / $2)")

    // 3. Square root: \sqrt{x} -> √(x)
    s = s.replace(REGEX_MATH_SQRT, "√($1)")

    // 4. Brackets: \left(, \right), etc.
    s = s.replace("\\left(", "(")
        .replace("\\right)", ")")
        .replace("\\left[", "[")
        .replace("\\right]", "]")
        .replace("\\left\\{", "{")
        .replace("\\right\\}", "}")
        .replace("\\{", "{")
        .replace("\\}", "}")

    // 5. Greek letters replacement
    for ((latex, unicode) in GREEK_MAP) {
        s = s.replace(latex, unicode)
    }

    // 6. Math symbols replacement
    for ((latex, unicode) in MATH_SYMBOLS_MAP) {
        s = s.replace(latex, unicode)
    }

    // 7. Common sub/superscripts
    s = s.replace("_{KL}", "_KL")
        .replace("_{total}", "_total")
        .replace("^{2}", "²")
        .replace("^2", "²")
        .replace("^{3}", "³")
        .replace("^3", "³")
        .replace("^{T}", "ᵀ")
        .replace("^T", "ᵀ")
        .replace("^{*}", "*")
        .replace("^{-1}", "⁻¹")

    // 8. Conditionals (z|x) -> (z | x)
    s = s.replace(REGEX_PAREN_BAR, "($1 | $2)")
    s = s.replace("||", " ‖ ")

    // 9. Strip surrounding $ and $$
    s = s.replace(Regex("""\$\$([^$\n]+)\$\$""")) { match ->
        match.groupValues[1].trim()
    }
    s = s.replace(Regex("""\$([^$\n]+)\$""")) { match ->
        match.groupValues[1].trim()
    }

    // 10. Clean duplicate spaces
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
                if (nextStar != -1) {
                    val boldContent = text.substring(i + 2, nextStar)
                    withStyle(SpanStyle(fontWeight = FontWeight.Bold)) {
                        append(boldContent)
                    }
                    i = nextStar + 2
                    continue
                } else {
                    val boldContent = text.substring(i + 2)
                    if (boldContent.isNotEmpty()) {
                        withStyle(SpanStyle(fontWeight = FontWeight.Bold)) {
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
