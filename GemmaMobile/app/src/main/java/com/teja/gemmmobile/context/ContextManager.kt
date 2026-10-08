package com.teja.gemmmobile.context

import com.teja.gemmmobile.ui.ChatMessage
import com.teja.gemmmobile.ui.MessageRole
import kotlin.math.max

/**
 * Token-aware context manager for Gemma 4 on-device execution.
 * Intelligently packages system instruction, long-term user memories,
 * conversation history, and tool feedback within safe KV-cache limits.
 */
class ContextManager(
    private val maxContextTokens: Int = 1100 // Safe limit guaranteeing (Prompt 1100 + Output 640 + Thinking 192 <= 2048)
) {

    companion object {
        /**
         * Conservative token estimator (~3.5 chars per token for typical mixed text/code).
         */
        fun estimateTokens(text: String): Int {
            if (text.isEmpty()) return 0
            return max(1, (text.length * 10) / 35)
        }
    }

    /**
     * Constructs the complete, optimized prompt ready for Gemma inference.
     */
    fun buildPrompt(
        systemPrompt: String,
        toolsDocumentation: String = "",
        memoryContext: String = "",
        conversationHistory: List<ChatMessage>,
        currentPrompt: String,
        searchContext: String = "",
        toolResultsContext: String = ""
    ): String {
        val budget = maxContextTokens

        val sysBlock = buildString {
            if (systemPrompt.isNotBlank()) {
                appendLine(systemPrompt.trim())
                appendLine()
            }
            if (toolsDocumentation.isNotBlank()) {
                appendLine(toolsDocumentation.trim())
                appendLine()
            }
            if (memoryContext.isNotBlank()) {
                appendLine(memoryContext.trim())
                appendLine()
            }
        }.trim()

        val sysTokens = estimateTokens(sysBlock)

        // Ensure user prompt / search context fits within prompt allocation
        val maxCurrentPromptChars = 2000
        val boundedPrompt = if (currentPrompt.length > maxCurrentPromptChars) {
            currentPrompt.take(maxCurrentPromptChars) + "\n...[truncated to fit memory]"
        } else {
            currentPrompt
        }

        val boundedSearch = if (searchContext.length > 1200) {
            searchContext.take(1200) + "\n..."
        } else {
            searchContext
        }

        val currentBlock = buildString {
            if (boundedSearch.isNotBlank()) {
                appendLine("Real-Time Web Search Results:")
                appendLine(boundedSearch.trim())
                appendLine()
            }
            if (toolResultsContext.isNotBlank()) {
                appendLine("Tool Execution Results:")
                appendLine(toolResultsContext.trim())
                appendLine()
            }
            appendLine("User: ${boundedPrompt.trim()}")
        }.trim()

        val currentTokens = estimateTokens(currentBlock)
        val remainingBudget = max(0, budget - sysTokens - currentTokens)

        val selectedHistory = mutableListOf<String>()
        var historyTokensUsed = 0

        if (remainingBudget > 5) {
            val eligibleHistory = conversationHistory
                .filter { it.text.isNotBlank() }
                .takeLast(8)

            for (msg in eligibleHistory.reversed()) {
                val roleName = if (msg.role == MessageRole.USER) "User" else "Assistant"
                // Cap single history message text to 300 chars to avoid one giant old message eating all history budget
                val cleanText = if (msg.text.length > 300) msg.text.take(300) + "..." else msg.text.trim()
                val line = "$roleName: $cleanText"
                val lineTokens = estimateTokens(line)
                if (historyTokensUsed + lineTokens <= remainingBudget) {
                    selectedHistory.add(0, line)
                    historyTokensUsed += lineTokens
                } else {
                    break
                }
            }
        }

        return buildString {
            if (sysBlock.isNotBlank()) {
                appendLine(sysBlock)
                appendLine()
            }
            if (selectedHistory.isNotEmpty()) {
                appendLine("[Recent Conversation History]")
                selectedHistory.forEach { appendLine(it) }
                appendLine()
            }
            appendLine(currentBlock)
        }.trim()
    }
}
