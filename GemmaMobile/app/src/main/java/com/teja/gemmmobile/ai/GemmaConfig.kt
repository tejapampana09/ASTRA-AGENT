package com.teja.gemmmobile.ai

/**
 * Hardware compute acceleration preference for Gemma 4 local inference.
 */
enum class PreferredBackend(val displayName: String) {
    CPU("CPU (Recommended - Smooth & Stable)"),
    GPU("GPU (High Speed - May cause system stutter)")
}

/**
 * User-configurable parameters for Gemma 4 E2B inference via LiteRT-LM.
 */
data class GemmaConfig(
    val temperature: Float = 0.65f,
    val maxTokens: Int = 1024,
    val topP: Float = 0.90f,
    val topK: Int = 40,
    val enableThinking: Boolean = false,
    val thinkingBudget: Int = 0,
    val systemPrompt: String = DEFAULT_SYSTEM_PROMPT,
    val preferredBackend: PreferredBackend = PreferredBackend.CPU
) {
    companion object {
        const val DEFAULT_SYSTEM_PROMPT = """You are ASTRA, an intelligent AI assistant — friendly, conversational, and helpful like ChatGPT.

## RULES
1. **Language**: Reply in the SAME language as the user. If Telugu/Telugu words (enti, cheppu, gurinchi, etc.), reply in natural Telugu. If English, reply in English.
2. **Completeness**: Provide clear, complete explanations (2-4 paragraphs or structured bullet points). Never cut off mid-thought or leave sentences unfinished.
3. **Follow-up**: Conclude with a helpful follow-up question or logical next topic to explore.
4. **Formatting**: Use **bold** for key concepts, bullet points for lists, and `code` for technical terms."""

        val DEFAULT = GemmaConfig()
    }
}
