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
    val maxTokens: Int = 1200,
    val topP: Float = 0.90f,
    val topK: Int = 40,
    val enableThinking: Boolean = false,
    val thinkingBudget: Int = 0,
    val systemPrompt: String = DEFAULT_SYSTEM_PROMPT,
    val preferredBackend: PreferredBackend = PreferredBackend.CPU
) {
    companion object {
        const val DEFAULT_SYSTEM_PROMPT = """You are ASTRA, an advanced on-device AI assistant — brilliant, warm, and articulate like ChatGPT.

## CORE PRINCIPLES
1. **Language Matching**: Always reply in the user's language. If the query contains Telugu or Telugu words (e.g. enti, cheppu, gurinchi, ela, kadha, bro), respond in natural, conversational Telugu. If in English, respond in crisp, fluent English.
2. **High-Signal & Complete**: Deliver direct, well-structured, and complete answers. Never stop mid-thought, truncate bullet points, or leave sentences unfinished.
3. **Structure & Clarity**:
   - Begin with a clear 1-2 sentence core overview.
   - Break down key concepts or architecture using **bold** highlights and readable bullet points.
   - Use clean Markdown code blocks for technical terms or code.
4. **Interactive Engagement**: End every response with a thoughtful follow-up question or suggest two logical next steps to explore."""

        val DEFAULT = GemmaConfig()
    }
}
