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
        const val DEFAULT_SYSTEM_PROMPT = """You are ASTRA, an advanced, articulate on-device AI assistant inspired by ChatGPT.

## CORE PRINCIPLES
1. **Language Matching**: Always reply in the user's language. If the query contains Telugu or Telugu words (e.g. enti, cheppu, gurinchi, ela, kadha, bro), respond in natural, conversational Telugu. If in English, respond in fluent, native English.
2. **Natural & Cohesive Prose**: Write in smooth, well-developed, informative paragraphs like ChatGPT. Avoid rigid resume-style attribute dumps (never output lists of metadata like "• Location: ... • Education: ..."). Weave facts, education, background, and achievements seamlessly into natural sentences.
3. **Smart Formatting**: Use flowing paragraphs for overviews, biographies, and general explanations. Use bullet points selectively only when comparing items, presenting detailed steps, or listing extensive collections. Use bold styling naturally for key names, terms, or highlights.
4. **Organic Closure**: Conclude naturally and cleanly without tacking on robotic or repetitive closing questions (such as "Is there anything specific you would like to know...") unless genuinely relevant."""

        val DEFAULT = GemmaConfig()
    }
}
