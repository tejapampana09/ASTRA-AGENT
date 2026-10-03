package com.teja.gemmmobile.ui

import android.widget.Toast
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
    modifier: Modifier = Modifier
) {
    val textColor = if (isUser) {
        MaterialTheme.colorScheme.onPrimaryContainer
    } else {
        MaterialTheme.colorScheme.onSurface
    }

    val linkColor = if (isUser) {
        MaterialTheme.colorScheme.primary
    } else {
        Color(0xFF1976D2) // Crisp, distinct blue for links in ChatGPT style
    }

    val codeBgColor = if (isUser) {
        MaterialTheme.colorScheme.primary.copy(alpha = 0.15f)
    } else {
        MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.6f)
    }

    val blocks = remember(text) { parseMarkdownBlocks(text) }

    Column(
        modifier = modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(6.dp)
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
                    val sanitized = sanitizeMarkdown(block.content)
                    val lines = sanitized.lines()

                    for ((index, line) in lines.withIndex()) {
                        val trimmed = line.trim()
                        if (trimmed.isEmpty()) {
                            if (index > 0 && index < lines.size - 1) {
                                Spacer(modifier = Modifier.height(3.dp))
                            }
                            continue
                        }

                        when {
                            // Header 1, 2, 3
                            trimmed.startsWith("### ") -> {
                                ClickableMarkdownLine(
                                    annotatedText = buildInlineMarkdown(
                                        trimmed.removePrefix("### ").trim(),
                                        textColor,
                                        linkColor,
                                        codeBgColor
                                    ),
                                    style = MaterialTheme.typography.titleSmall.copy(
                                        fontWeight = FontWeight.Bold,
                                        color = textColor
                                    ),
                                    modifier = Modifier.padding(top = 4.dp, bottom = 2.dp)
                                )
                            }

                            trimmed.startsWith("## ") -> {
                                ClickableMarkdownLine(
                                    annotatedText = buildInlineMarkdown(
                                        trimmed.removePrefix("## ").trim(),
                                        textColor,
                                        linkColor,
                                        codeBgColor
                                    ),
                                    style = MaterialTheme.typography.titleMedium.copy(
                                        fontWeight = FontWeight.Bold,
                                        color = textColor
                                    ),
                                    modifier = Modifier.padding(top = 6.dp, bottom = 2.dp)
                                )
                            }

                            trimmed.startsWith("# ") -> {
                                ClickableMarkdownLine(
                                    annotatedText = buildInlineMarkdown(
                                        trimmed.removePrefix("# ").trim(),
                                        textColor,
                                        linkColor,
                                        codeBgColor
                                    ),
                                    style = MaterialTheme.typography.titleLarge.copy(
                                        fontWeight = FontWeight.Bold,
                                        color = textColor
                                    ),
                                    modifier = Modifier.padding(top = 8.dp, bottom = 4.dp)
                                )
                            }

                            // Bullet point: * or - or •
                            trimmed.startsWith("* ") || trimmed.startsWith("- ") || trimmed.startsWith("• ") -> {
                                val content = when {
                                    trimmed.startsWith("* ") -> trimmed.removePrefix("* ")
                                    trimmed.startsWith("- ") -> trimmed.removePrefix("- ")
                                    else -> trimmed.removePrefix("• ")
                                }.trim()

                                Row(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(start = 4.dp),
                                    verticalAlignment = Alignment.Top
                                ) {
                                    Text(
                                        text = "•",
                                        style = MaterialTheme.typography.bodyMedium,
                                        fontWeight = FontWeight.Bold,
                                        color = textColor,
                                        modifier = Modifier.padding(end = 6.dp)
                                    )
                                    ClickableMarkdownLine(
                                        annotatedText = buildInlineMarkdown(content, textColor, linkColor, codeBgColor),
                                        style = MaterialTheme.typography.bodyMedium.copy(color = textColor, lineHeight = 22.sp),
                                        modifier = Modifier.weight(1f)
                                    )
                                }
                            }

                            // Numbered list: e.g. "1. " or "2. "
                            trimmed.matches(Regex("""^\d+\.\s+.*""")) -> {
                                val prefix = trimmed.substringBefore(". ") + "."
                                val content = trimmed.substringAfter(". ").trim()

                                Row(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(start = 4.dp),
                                    verticalAlignment = Alignment.Top
                                ) {
                                    Text(
                                        text = prefix,
                                        style = MaterialTheme.typography.bodyMedium,
                                        fontWeight = FontWeight.SemiBold,
                                        color = textColor,
                                        modifier = Modifier.padding(end = 6.dp)
                                    )
                                    ClickableMarkdownLine(
                                        annotatedText = buildInlineMarkdown(content, textColor, linkColor, codeBgColor),
                                        style = MaterialTheme.typography.bodyMedium.copy(color = textColor, lineHeight = 22.sp),
                                        modifier = Modifier.weight(1f)
                                    )
                                }
                            }

                            // Regular paragraph
                            else -> {
                                ClickableMarkdownLine(
                                    annotatedText = buildInlineMarkdown(trimmed, textColor, linkColor, codeBgColor),
                                    style = MaterialTheme.typography.bodyMedium.copy(color = textColor, lineHeight = 22.sp)
                                )
                            }
                        }
                    }
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

/**
 * ChatGPT-style scrollable, copyable Data Table View.
 */
@Composable
fun MarkdownTableView(
    headers: List<String>,
    rows: List<List<String>>,
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current
    val clipboard = LocalClipboardManager.current
    val scrollState = rememberScrollState()

    Surface(
        shape = RoundedCornerShape(10.dp),
        color = Color.White,
        border = BorderStroke(1.dp, Color(0xFFE5E5E5)),
        modifier = modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp)
    ) {
        Column {
            // Header Bar with "TABLE" and Copy button
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(Color(0xFFF7F7F8))
                    .padding(horizontal = 12.dp, vertical = 7.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "TABLE (${rows.size} rows)",
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.Bold,
                    color = Color(0xFF8E8E93),
                    fontSize = 11.sp
                )
                Text(
                    text = "📋 Copy",
                    style = MaterialTheme.typography.labelSmall,
                    color = Color(0xFF10A37F),
                    fontWeight = FontWeight.SemiBold,
                    fontSize = 12.sp,
                    modifier = Modifier
                        .clip(RoundedCornerShape(4.dp))
                        .clickable {
                            val csv = buildString {
                                appendLine(headers.joinToString(","))
                                rows.forEach { row -> appendLine(row.joinToString(",")) }
                            }
                            clipboard.setText(AnnotatedString(csv))
                            Toast.makeText(context, "Table copied to clipboard", Toast.LENGTH_SHORT).show()
                        }
                        .padding(horizontal = 6.dp, vertical = 2.dp)
                )
            }

            HorizontalDivider(color = Color(0xFFE5E5E5), thickness = 0.8.dp)

            // Horizontally scrollable table grid
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .horizontalScroll(scrollState)
                    .padding(horizontal = 6.dp, vertical = 6.dp)
            ) {
                Column {
                    // Header Row
                    Row(
                        modifier = Modifier
                            .background(Color(0xFFF4F4F4), RoundedCornerShape(6.dp))
                            .padding(vertical = 9.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        headers.forEach { header ->
                            Box(
                                modifier = Modifier
                                    .widthIn(min = 100.dp, max = 220.dp)
                                    .padding(horizontal = 10.dp)
                            ) {
                                Text(
                                    text = header.trim(),
                                    style = MaterialTheme.typography.labelMedium,
                                    fontWeight = FontWeight.Bold,
                                    color = Color(0xFF0D0D0D),
                                    fontSize = 13.sp
                                )
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(2.dp))

                    // Data Rows
                    rows.forEachIndexed { rowIndex, row ->
                        Row(
                            modifier = Modifier
                                .background(if (rowIndex % 2 == 0) Color.White else Color(0xFFFAFAFA))
                                .padding(vertical = 9.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            row.forEachIndexed { colIndex, cell ->
                                Box(
                                    modifier = Modifier
                                        .widthIn(min = 100.dp, max = 220.dp)
                                        .padding(horizontal = 10.dp)
                                ) {
                                    val cleanCell = cell.replace("\\_", "_").trim()
                                    Text(
                                        text = cleanCell,
                                        style = MaterialTheme.typography.bodySmall,
                                        color = Color(0xFF1E1E1E),
                                        fontSize = 12.5.sp,
                                        lineHeight = 17.sp
                                    )
                                }
                            }
                        }
                        if (rowIndex < rows.size - 1) {
                            HorizontalDivider(color = Color(0xFFF0F0F0), thickness = 0.5.dp)
                        }
                    }
                }
            }
        }
    }
}

/**
 * Parses raw text into alternating Code blocks, Tables, and regular Markdown blocks.
 */
fun parseMarkdownBlocks(input: String): List<MarkdownBlock> {
    val blocks = mutableListOf<MarkdownBlock>()
    val codeBlockRegex = Regex("""```([a-zA-Z0-9_+#.-]*)\s*\n([\s\S]*?)```""")
    var currentIndex = 0

    for (match in codeBlockRegex.findAll(input)) {
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
        val unclosedMatch = Regex("""```([a-zA-Z0-9_+#.-]*)\s*\n([\s\S]*)""").find(remaining)
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

    return if (blocks.isEmpty() && input.isNotBlank()) listOf(MarkdownBlock.Text(input)) else blocks
}

/**
 * Extracts Markdown tables from text and returns a sequence of Text and Table blocks.
 */
fun extractTablesAndText(text: String): List<MarkdownBlock> {
    val results = mutableListOf<MarkdownBlock>()
    val tableRegex = Regex("""(?m)^([ \t]*\|[^\n]+\|[ \t]*\n[ \t]*\|[-: |]+\|[ \t]*(?:\n[ \t]*\|[^\n]+\|[ \t]*)+)""")
    var lastIdx = 0

    for (match in tableRegex.findAll(text)) {
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

    val rawHeaders = headerLine.split("|").map { it.trim() }
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
            val rawCells = line.split("|").map { it.trim() }
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
 * Cleans unwanted math/LaTeX tokens and artifacts commonly generated by raw LLM checkpoints.
 */
fun sanitizeMarkdown(input: String): String {
    var s = input
    s = s.replace(Regex("""\$\s*\\text\{([^}]+)\}\s*\$"""), "$1")
    s = s.replace(Regex("""\$\s*\\mathrm\{([^}]+)\}\s*\$"""), "$1")
    s = s.replace(Regex("""\(\s*\\text\{([^}]+)\}\s*\)"""), "$1")
    s = s.replace(Regex("""\\text\{([^}]+)\}"""), "$1")
    s = s.replace(Regex("""\$([^$\n]+)\$"""), "$1")
    return s
}

/**
 * Parses inline spans: links, **bold**, *italic*, and `code` into an AnnotatedString with clickable URL annotations.
 */
fun buildInlineMarkdown(
    text: String,
    defaultColor: Color,
    linkColor: Color,
    codeBgColor: Color
): AnnotatedString {
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
                        val title = text.substring(i + 1, closeBracket)
                        val url = text.substring(closeBracket + 2, closeParen).trim()
                        if (url.startsWith("http://") || url.startsWith("https://")) {
                            pushStringAnnotation(tag = "URL", annotation = url)
                            withStyle(
                                SpanStyle(
                                    color = linkColor,
                                    textDecoration = TextDecoration.Underline,
                                    fontWeight = FontWeight.SemiBold
                                )
                            ) {
                                append(title)
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
                    pushStringAnnotation(tag = "URL", annotation = url)
                    withStyle(
                        SpanStyle(
                            color = linkColor,
                            textDecoration = TextDecoration.Underline,
                            fontWeight = FontWeight.SemiBold
                        )
                    ) {
                        append(url)
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
                }
            }

            append(text[i])
            i++
        }
    }
}
