package com.teja.gemmmobile.audio

import android.content.Context
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.util.Locale

class TtsManager(private val context: Context) : TextToSpeech.OnInitListener {

    private var tts: TextToSpeech? = null
    private var isInitialized = false

    private val _isSpeaking = MutableStateFlow(false)
    val isSpeaking: StateFlow<Boolean> = _isSpeaking.asStateFlow()

    private val _currentMessageId = MutableStateFlow<String?>(null)
    val currentMessageId: StateFlow<String?> = _currentMessageId.asStateFlow()

    init {
        tts = TextToSpeech(context.applicationContext, this)
    }

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            isInitialized = true
            tts?.language = Locale.getDefault()
            tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                override fun onStart(utteranceId: String?) {
                    _isSpeaking.value = true
                }

                override fun onDone(utteranceId: String?) {
                    _isSpeaking.value = false
                    _currentMessageId.value = null
                }

                @Deprecated("Deprecated in Java")
                override fun onError(utteranceId: String?) {
                    _isSpeaking.value = false
                    _currentMessageId.value = null
                }
            })
        }
    }

    fun speak(messageId: String, text: String) {
        if (!isInitialized || tts == null) return

        if (_isSpeaking.value && _currentMessageId.value == messageId) {
            stop()
            return
        }

        stop()
        _currentMessageId.value = messageId
        val cleanText = prepareTextForSpeech(text)
        if (cleanText.isBlank()) return

        val params = android.os.Bundle()
        params.putString(TextToSpeech.Engine.KEY_PARAM_UTTERANCE_ID, messageId)
        tts?.speak(cleanText, TextToSpeech.QUEUE_FLUSH, params, messageId)
    }

    fun stop() {
        tts?.stop()
        _isSpeaking.value = false
        _currentMessageId.value = null
    }

    fun release() {
        stop()
        tts?.shutdown()
        tts = null
        isInitialized = false
    }

    private fun prepareTextForSpeech(raw: String): String {
        var s = raw
        // Remove code blocks
        s = s.replace(Regex("""```[\s\S]*?```"""), " Code block omitted. ")
        // Remove inline code
        s = s.replace(Regex("""`([^`]+)`"""), "$1")
        // Remove URLs
        s = s.replace(Regex("""https?://\S+"""), " link ")
        // Remove markdown headers and bullets
        s = s.replace(Regex("""^#{1,6}\s+""", RegexOption.MULTILINE), "")
        s = s.replace(Regex("""^[*•-]\s+""", RegexOption.MULTILINE), "")
        s = s.replace(Regex("""\*\*([^*]+)\*\*"""), "$1")
        s = s.replace(Regex("""\*([^*]+)\*"""), "$1")
        return s.trim()
    }
}
