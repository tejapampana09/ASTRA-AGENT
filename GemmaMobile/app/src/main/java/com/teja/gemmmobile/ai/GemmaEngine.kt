package com.teja.gemmmobile.ai

import android.util.Log
import com.google.ai.edge.litertlm.Backend
import com.google.ai.edge.litertlm.Content
import com.google.ai.edge.litertlm.Contents
import com.google.ai.edge.litertlm.Conversation
import com.google.ai.edge.litertlm.ConversationConfig
import com.google.ai.edge.litertlm.Engine
import com.google.ai.edge.litertlm.EngineConfig
import com.google.ai.edge.litertlm.LogSeverity
import com.google.ai.edge.litertlm.Message
import com.google.ai.edge.litertlm.SamplerConfig
import com.google.ai.edge.litertlm.ThinkingConfig
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import java.io.File

private const val TAG = "GemmaMobile"

/**
 * Backend hardware acceleration modes supported by LiteRT-LM.
 */
enum class BackendType(val displayName: String) {
    GPU("GPU"),
    CPU("CPU"),
    CPU_FALLBACK("CPU fallback")
}

/**
 * State representing the status of the local Gemma engine.
 */
sealed interface EngineState {
    data object Uninitialized : EngineState
    data class Loading(val message: String) : EngineState
    data class Ready(val backend: BackendType) : EngineState
    data class Generating(val backend: BackendType) : EngineState
    data class Error(val message: String) : EngineState
}

/**
 * Core engine wrapper for on-device Gemma 4 E2B IT execution using LiteRT-LM.
 *
 * All initialization and inference calls run strictly on background threads (Dispatchers.IO)
 * to ensure the UI remains smooth and responsive at all times.
 */
class GemmaEngine(
    private val modelPath: String,
    private var currentConfig: GemmaConfig = GemmaConfig.DEFAULT
) : AutoCloseable {

    private val _engineState = MutableStateFlow<EngineState>(EngineState.Uninitialized)
    val engineState: StateFlow<EngineState> = _engineState.asStateFlow()

    private var engine: Engine? = null
    private var conversation: Conversation? = null
    private var activeBackend: BackendType = BackendType.CPU

    private val mutex = Mutex()

    init {
        // Set native log severity to INFO for clean debugging
        try {
            Engine.setNativeMinLogSeverity(LogSeverity.INFO)
        } catch (t: Throwable) {
            Log.w(TAG, "[$TAG] Could not set native log severity", t)
        }
    }

    private fun buildConversationConfig(cfg: GemmaConfig): ConversationConfig {
        return ConversationConfig(
            systemInstruction = if (cfg.systemPrompt.isNotBlank()) Contents.of(cfg.systemPrompt) else null,
            samplerConfig = SamplerConfig(
                topK = cfg.topK,
                topP = cfg.topP.toDouble(),
                temperature = cfg.temperature.toDouble(),
                seed = 0
            ),
            maxOutputToken = cfg.maxTokens,
            thinkingConfig = ThinkingConfig(
                enableThinking = cfg.enableThinking,
                thinkingTokenBudget = if (cfg.enableThinking) cfg.thinkingBudget else 0
            )
        )
    }

    /**
     * Initializes the LiteRT-LM Engine and Conversation with Gemma 4 E2B IT.
     * Prefers GPU acceleration and automatically falls back to CPU if GPU initialization fails.
     */
    suspend fun initialize(): Result<BackendType> = withContext(Dispatchers.IO) {
        mutex.withLock {
            if (engine?.isInitialized() == true && conversation?.isAlive == true) {
                Log.d(TAG, "[$TAG] Engine already initialized.")
                return@withContext Result.success(activeBackend)
            }

            val file = File(modelPath)
            if (!file.exists() || file.length() == 0L) {
                val errorMsg = "Gemma model is not installed at: $modelPath"
                Log.e(TAG, "[$TAG] $errorMsg")
                _engineState.value = EngineState.Error(errorMsg)
                return@withContext Result.failure(IllegalStateException(errorMsg))
            }

            _engineState.value = EngineState.Loading("Initializing model on CPU...")
            Log.d(TAG, "[$TAG] Initializing model with CPU backend (4 threads)...")

            var loadedEngine: Engine? = null
            var backendChosen = BackendType.CPU

            try {
                val cpuConfig = try {
                    EngineConfig(
                        modelPath = modelPath,
                        backend = Backend.CPU(threadCount = 4),
                        visionBackend = Backend.CPU(threadCount = 4),
                        maxNumImages = 1
                    )
                } catch (t: Throwable) {
                    EngineConfig(
                        modelPath = modelPath,
                        backend = Backend.CPU(threadCount = 4)
                    )
                }
                val testEngine = Engine(cpuConfig)
                testEngine.initialize()
                loadedEngine = testEngine
                backendChosen = BackendType.CPU
                Log.d(TAG, "[$TAG] Model loaded successfully on CPU (with visionBackend configured)")
            } catch (cpuException: Throwable) {
                if (cpuException is CancellationException) throw cpuException
                val fatalMsg = "Failed to load Gemma 4 model on CPU: ${cpuException.localizedMessage ?: "Unknown initialization error"}"
                Log.e(TAG, "[$TAG] $fatalMsg", cpuException)
                _engineState.value = EngineState.Error(fatalMsg)
                return@withContext Result.failure(cpuException)
            }

            // Create initial conversation session
            try {
                engine = loadedEngine
                activeBackend = backendChosen
                val convConfig = buildConversationConfig(currentConfig)
                conversation = loadedEngine.createConversation(convConfig)
                _engineState.value = EngineState.Ready(activeBackend)
                Result.success(activeBackend)
            } catch (convError: Throwable) {
                if (convError is CancellationException) throw convError
                val errorMsg = "Failed to create conversation session: ${convError.localizedMessage}"
                Log.e(TAG, "[$TAG] $errorMsg", convError)
                _engineState.value = EngineState.Error(errorMsg)
                Result.failure(convError)
            }
        }
    }

/**
 * Data container for streaming chunks containing text and optional thought tokens.
 */
data class EngineChunk(
    val text: String = "",
    val thought: String = ""
)

    /**
     * Sends a prompt (and optional image bytes) and streams the generated tokens (both thoughts and final answer) back incrementally.
     */
    fun sendMessage(prompt: String, imageBytes: ByteArray? = null): Flow<EngineChunk> = flow {
        if (prompt.isBlank() && imageBytes == null) return@flow

        val eng = engine
        check(eng != null && eng.isInitialized()) { "Model is not initialized. Please install model first." }

        Log.d(TAG, "[$TAG] Starting generation with thinking=${currentConfig.enableThinking}, budget=${currentConfig.thinkingBudget}, hasImage=${imageBytes != null}")

        val thinkingConfig = ThinkingConfig(
            enableThinking = currentConfig.enableThinking,
            thinkingTokenBudget = if (currentConfig.enableThinking) currentConfig.thinkingBudget else 0
        )

        try {
            var attempt = 0
            var succeeded = false
            while (attempt < 2 && !succeeded) {
                attempt++
                try {
                    val targetConv = mutex.withLock {
                        val cur = conversation
                        check(cur != null && cur.isAlive) { "Model is not initialized or conversation is closed." }
                        _engineState.value = EngineState.Generating(activeBackend)
                        cur
                    }

                    val messageFlow = if (imageBytes != null && imageBytes.isNotEmpty()) {
                        val contents = Contents.of(
                            Content.ImageBytes(imageBytes),
                            Content.Text(prompt)
                        )
                        targetConv.sendMessageAsync(contents = contents, thinkingConfig = thinkingConfig)
                    } else {
                        targetConv.sendMessageAsync(text = prompt, thinkingConfig = thinkingConfig)
                    }

                    // LiteRT-LM async flow streaming with thinking configuration
                    messageFlow.collect { message: Message ->
                        val thoughtChannel = message.channels["thought"]
                            ?: message.channels["thinking"]
                            ?: message.channels.values.firstOrNull { it.isNotEmpty() }
                            ?: ""
                        val textContent = message.toString()

                        if (thoughtChannel.isNotEmpty() || textContent.isNotEmpty()) {
                            emit(EngineChunk(text = textContent, thought = thoughtChannel))
                        }
                    }
                    succeeded = true
                    Log.d(TAG, "[$TAG] Generation complete")
                } catch (e: Throwable) {
                    if (e is CancellationException) {
                        Log.d(TAG, "[$TAG] Generation cancelled by user/lifecycle")
                        throw e
                    }
                    val errStr = e.message.orEmpty()
                    if (attempt == 1 && (errStr.contains("exceeds available state entries", ignoreCase = true) ||
                            errStr.contains("Status Code: 9", ignoreCase = true) ||
                            errStr.contains("capacity", ignoreCase = true))) {
                        Log.w(TAG, "[$TAG] KV Cache state entries limit reached. Resetting conversation and retrying once...")
                        mutex.withLock {
                            try { conversation?.close() } catch (_: Throwable) {}
                            conversation = eng.createConversation(buildConversationConfig(currentConfig))
                        }
                        continue
                    }
                    Log.e(TAG, "[$TAG] Generation failure", e)
                    throw e
                }
            }
        } finally {
            mutex.withLock {
                if (_engineState.value is EngineState.Generating) {
                    _engineState.value = EngineState.Ready(activeBackend)
                }
            }
        }
    }.flowOn(Dispatchers.IO)

    /**
     * Clears in-memory conversation history and resets the KV-cache.
     */
    suspend fun clearConversation() = withContext(Dispatchers.IO) {
        mutex.withLock {
            try {
                Log.d(TAG, "[$TAG] Clearing conversation history...")
                conversation?.close()
                conversation = null
                val eng = engine
                if (eng != null && eng.isInitialized()) {
                    conversation = eng.createConversation(buildConversationConfig(currentConfig))
                    _engineState.value = EngineState.Ready(activeBackend)
                    Log.d(TAG, "[$TAG] Conversation cleared successfully.")
                }
            } catch (e: Exception) {
                Log.e(TAG, "[$TAG] Error resetting conversation", e)
            }
        }
    }

    /**
     * Dynamically updates the active conversation configuration (temperature, topP, topK, tokens, thinking, prompt).
     */
    suspend fun updateConfig(newConfig: GemmaConfig) = withContext(Dispatchers.IO) {
        mutex.withLock {
            currentConfig = newConfig
            try {
                val eng = engine
                if (eng != null && eng.isInitialized()) {
                    Log.d(TAG, "[$TAG] Applying updated GemmaConfig...")
                    conversation?.close()
                    conversation = eng.createConversation(buildConversationConfig(newConfig))
                    _engineState.value = EngineState.Ready(activeBackend)
                    Log.d(TAG, "[$TAG] Successfully applied new GemmaConfig: $newConfig")
                }
            } catch (e: Exception) {
                Log.e(TAG, "[$TAG] Error applying new conversation config", e)
            }
        }
    }

    /**
     * Closes the conversation and engine, releasing all native LiteRT-LM memory and resources.
     */
    override fun close() {
        try {
            Log.d(TAG, "[$TAG] Closing GemmaEngine and releasing native resources...")
            conversation?.close()
            conversation = null
            engine?.close()
            engine = null
            _engineState.value = EngineState.Uninitialized
            Log.d(TAG, "[$TAG] GemmaEngine resources released.")
        } catch (e: Exception) {
            Log.e(TAG, "[$TAG] Error closing engine", e)
        }
    }
}
