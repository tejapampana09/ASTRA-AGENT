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

    private fun buildConversationConfig(
        cfg: GemmaConfig,
        effectiveThinking: Boolean = cfg.enableThinking,
        dynamicMaxOutput: Int? = null,
        systemInstructionText: String? = null
    ): ConversationConfig {
        val thinkBudget = if (effectiveThinking) minOf(cfg.thinkingBudget, 160) else 0
        val maxOut = dynamicMaxOutput ?: maxOf(400, minOf(cfg.maxTokens, 1024))
        val sysContent = if (!systemInstructionText.isNullOrBlank()) {
            Contents.of(Content.Text(systemInstructionText))
        } else null
        return ConversationConfig(
            systemInstruction = sysContent,
            samplerConfig = SamplerConfig(
                topK = cfg.topK,
                topP = cfg.topP.toDouble(),
                temperature = cfg.temperature.toDouble(),
                seed = 0
            ),
            maxOutputToken = maxOut,
            thinkingConfig = ThinkingConfig(
                enableThinking = effectiveThinking,
                thinkingTokenBudget = thinkBudget
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

            if (file.length() < 1_900_000_000L) {
                val currentMb = file.length() / (1024 * 1024)
                val errorMsg = "Model file is incomplete ($currentMb MB). Expected ~2.58 GB (2588 MB). Please re-download or push complete model."
                Log.e(TAG, "[$TAG] $errorMsg")
                _engineState.value = EngineState.Error(errorMsg)
                return@withContext Result.failure(IllegalStateException(errorMsg))
            }

            _engineState.value = EngineState.Loading("Initializing model on GPU...")
            Log.i(TAG, "[$TAG] Trying GPU backend from $modelPath (${file.length()} bytes)...")

            var loadedEngine: Engine? = null
            var backendChosen = BackendType.GPU
            var lastGpuError: String? = null
            // Cap thread count to at most 4 to prevent heavy multi-core CPU thermal throttling & overheating
            val threadCount = minOf(4, Runtime.getRuntime().availableProcessors().coerceAtLeast(2))

            // Attempt 1: GPU with Vision
            try {
                Log.d(TAG, "[$TAG] Attempting GPU + Vision...")
                val config = EngineConfig(
                    modelPath = modelPath,
                    backend = Backend.GPU(),
                    visionBackend = Backend.GPU(),
                    maxNumImages = 1
                )
                val testEngine = Engine(config)
                testEngine.initialize()
                loadedEngine = testEngine
                backendChosen = BackendType.GPU
                Log.i(TAG, "[$TAG] Model loaded successfully on GPU (Vision + Text)")
            } catch (e1: Throwable) {
                lastGpuError = e1.message ?: "Unknown GPU error"
                Log.w(TAG, "[$TAG] GPU + Vision failed: ${e1.message}. Attempting pure GPU text...")
                // Attempt 2: Pure GPU text
                try {
                    val config = EngineConfig(
                        modelPath = modelPath,
                        backend = Backend.GPU()
                    )
                    val testEngine = Engine(config)
                    testEngine.initialize()
                    loadedEngine = testEngine
                    backendChosen = BackendType.GPU
                    Log.i(TAG, "[$TAG] Model loaded successfully on GPU (Text only)")
                } catch (e2: Throwable) {
                    lastGpuError = e2.message ?: lastGpuError
                    Log.w(TAG, "[$TAG] GPU initialization failed: $lastGpuError")
                    Log.i(TAG, "[$TAG] Falling back to CPU")
                    _engineState.value = EngineState.Loading("Falling back to CPU...")

                    // Attempt 3: CPU with Vision
                    try {
                        val config = EngineConfig(
                            modelPath = modelPath,
                            backend = Backend.CPU(threadCount = threadCount),
                            visionBackend = Backend.CPU(threadCount = threadCount),
                            maxNumImages = 1
                        )
                        val testEngine = Engine(config)
                        testEngine.initialize()
                        loadedEngine = testEngine
                        backendChosen = BackendType.CPU_FALLBACK
                        Log.i(TAG, "[$TAG] Model loaded successfully on CPU fallback (Vision + Text)")
                    } catch (e3: Throwable) {
                        Log.w(TAG, "[$TAG] CPU + Vision failed: ${e3.message}. Attempting pure CPU text...")
                        // Attempt 4: Pure CPU text
                        try {
                            val config = EngineConfig(
                                modelPath = modelPath,
                                backend = Backend.CPU(threadCount = threadCount)
                            )
                            val testEngine = Engine(config)
                            testEngine.initialize()
                            loadedEngine = testEngine
                            backendChosen = BackendType.CPU_FALLBACK
                            Log.i(TAG, "[$TAG] Model loaded successfully on CPU fallback (Text only)")
                        } catch (fatal: Throwable) {
                            if (fatal is CancellationException) throw fatal
                            val fatalMsg = if (lastGpuError != null) {
                                "Failed to load model: GPU error: [$lastGpuError]. CPU error: [${fatal.localizedMessage}]"
                            } else {
                                "Failed to load model: ${fatal.localizedMessage ?: "Unknown initialization error"}"
                            }
                            Log.e(TAG, "[$TAG] $fatalMsg", fatal)
                            _engineState.value = EngineState.Error(fatalMsg)
                            return@withContext Result.failure(Exception(fatalMsg, fatal))
                        }
                    }
                }
            }

            // Create initial conversation session
            try {
                engine = loadedEngine
                activeBackend = backendChosen
                val convConfig = buildConversationConfig(currentConfig)
                conversation = try {
                    loadedEngine.createConversation(convConfig)
                } catch (convFallback: Throwable) {
                    Log.w(TAG, "[$TAG] Custom conversation config failed, falling back to default: ${convFallback.message}")
                    loadedEngine.createConversation()
                }
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
    fun sendMessage(
        prompt: String,
        systemInstruction: String? = null,
        imageBytes: ByteArray? = null,
        enableThinkingOverride: Boolean? = null
    ): Flow<EngineChunk> = flow {
        if (prompt.isBlank() && imageBytes == null) return@flow

        val eng = engine
        check(eng != null && eng.isInitialized()) { "Model is not initialized. Please install model first." }

        val effectiveSysPrompt = systemInstruction ?: currentConfig.systemPrompt
        val promptTokens = com.teja.gemmmobile.context.ContextManager.estimateTokens(prompt) +
            com.teja.gemmmobile.context.ContextManager.estimateTokens(effectiveSysPrompt)
        val effectiveThinking = enableThinkingOverride ?: currentConfig.enableThinking
        val effectiveThinkingBudget = if (effectiveThinking) minOf(currentConfig.thinkingBudget, 160) else 0

        // Dynamically compute the maximum possible output token budget that fits safely within the 2048 KV cache.
        val dynamicMaxOutput = maxOf(300, minOf(currentConfig.maxTokens, 2048 - promptTokens - effectiveThinkingBudget - 64))
        Log.d(TAG, "[$TAG] Starting generation with promptTokens=$promptTokens, maxOutput=$dynamicMaxOutput, thinking=$effectiveThinking, thinkBudget=$effectiveThinkingBudget, hasImage=${imageBytes != null}")

        val thinkingConfig = ThinkingConfig(
            enableThinking = effectiveThinking,
            thinkingTokenBudget = effectiveThinkingBudget
        )

        try {
            var attempt = 0
            var succeeded = false
            while (attempt < 2 && !succeeded) {
                attempt++
                try {
                    val targetConv = mutex.withLock {
                        // Always create a fresh, clean conversation session per turn so LiteRT-LM's
                        // native KV cache never accumulates old turns and exceeds the 2048 token limit.
                        // Context and history are managed strictly within budget by ContextManager.
                        try { conversation?.close() } catch (_: Throwable) {}
                        val cur = eng.createConversation(
                            buildConversationConfig(
                                currentConfig,
                                effectiveThinking,
                                dynamicMaxOutput,
                                systemInstructionText = effectiveSysPrompt
                            )
                        )
                        conversation = cur
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

                    messageFlow.collect { message: Message ->
                        val thoughtChannel = message.channels["thought"]
                            ?: message.channels["thinking"]
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
                    if (errStr.contains("exceeds available state entries", ignoreCase = true) ||
                        errStr.contains("Status Code: 9", ignoreCase = true) ||
                        errStr.contains("capacity", ignoreCase = true)) {
                        Log.i(TAG, "[$TAG] Reached KV cache capacity limit cleanly. Finalizing generated response without error.")
                        succeeded = true
                        break
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

    fun resetToReady() {
        if (_engineState.value is EngineState.Generating) {
            _engineState.value = EngineState.Ready(activeBackend)
        }
    }

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
