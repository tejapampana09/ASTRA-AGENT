package com.teja.gemmmobile.ai

/**
 * User-configurable parameters for Gemma 4 E2B inference via LiteRT-LM.
 */
data class GemmaConfig(
    val temperature: Float = 0.8f,
    val maxTokens: Int = 1024,
    val topP: Float = 0.95f,
    val topK: Int = 40,
    val enableThinking: Boolean = true,
    val thinkingBudget: Int = 512,
    val systemPrompt: String = DEFAULT_SYSTEM_PROMPT
) {
    companion object {
        const val DEFAULT_SYSTEM_PROMPT = "You are Gemma, a highly capable, intelligent AI assistant. When analyzing images, screenshots, or documents, inspect all visual elements thoroughly. Accurately transcribe any text, numbers, handwriting, or records verbatim. Format any tabular or structured data into clean Markdown tables with column headers. Provide clear, precise, and well-organized responses."

        val DEFAULT = GemmaConfig()
    }
}
