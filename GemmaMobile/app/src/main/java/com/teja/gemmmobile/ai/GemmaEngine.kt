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
    private var currentConfig: GemmaConfig = GemmaConfig.DEFAULT,
    private val cacheDirPath: String? = null
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

            // Lower thread priority to background so that reading 2.58 GB weights and shader compilation
            // does NOT starve the Android Main/RenderThread, preventing system UI hangs and stutters.
            try {
                android.os.Process.setThreadPriority(android.os.Process.THREAD_PRIORITY_BACKGROUND)
            } catch (_: Throwable) {}

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

            val preferCpu = currentConfig.preferredBackend == PreferredBackend.CPU

            _engineState.value = EngineState.Loading(if (preferCpu) "Initializing model on CPU..." else "Initializing model on GPU...")
            Log.i(TAG, "[$TAG] Loading model with preferred backend: ${currentConfig.preferredBackend} from $modelPath (${file.length()} bytes)...")

            // Brief yield so the UI Composables can render the loading state smoothly
            kotlinx.coroutines.delay(100)
            kotlinx.coroutines.yield()

            val effectiveCacheDir = cacheDirPath ?: File(File(modelPath).parentFile ?: File("."), "litert_cache").apply { mkdirs() }.absolutePath
            File(effectiveCacheDir).mkdirs()
            var loadedEngine: Engine? = null
            var backendChosen = if (preferCpu) BackendType.CPU else BackendType.GPU
            var testEngine: Engine? = null

            if (preferCpu) {
                // Initialize directly on CPU: Smooth, responsive, zero GPU lockups, zero phone freezing!
                // Uses CPU vision with 2 threads to leave UI/SurfaceFlinger cores free
                var cpuEngineLoaded = false
                try {
                    Log.d(TAG, "[$TAG] Initializing CPU model with CPU vision backend (2 threads) and 2048 token budget...")
                    val config = EngineConfig(
                        modelPath = modelPath,
                        backend = Backend.CPU(threadCount = 4),
                        visionBackend = Backend.CPU(threadCount = 2),
                        maxNumTokens = 2048,
                        maxNumImages = 1,
                        cacheDir = effectiveCacheDir
                    )
                    testEngine = Engine(config)
                    testEngine.initialize()
                    loadedEngine = testEngine
                    backendChosen = BackendType.CPU
                    cpuEngineLoaded = true
                    Log.i(TAG, "[$TAG] Model loaded successfully on CPU with CPU vision backend")
                } catch (cpuVisionErr: Throwable) {
                    try { testEngine?.close() } catch (_: Throwable) {}
                    testEngine = null
                    Log.w(TAG, "[$TAG] CPU vision (2 threads) failed: ${cpuVisionErr.message}. Trying GPU vision backend...")
                }

                if (!cpuEngineLoaded) {
                    try {
                        Log.d(TAG, "[$TAG] Initializing CPU model with GPU vision backend...")
                        val config = EngineConfig(
                            modelPath = modelPath,
                            backend = Backend.CPU(threadCount = 4),
                            visionBackend = Backend.GPU(),
                            maxNumTokens = 2048,
                            maxNumImages = 1,
                            cacheDir = effectiveCacheDir
                        )
                        testEngine = Engine(config)
                        testEngine.initialize()
                        loadedEngine = testEngine
                        backendChosen = BackendType.CPU
                        cpuEngineLoaded = true
                        Log.i(TAG, "[$TAG] Model loaded successfully on CPU with GPU vision backend")
                    } catch (gpuVisionErr: Throwable) {
                        try { testEngine?.close() } catch (_: Throwable) {}
                        testEngine = null
                        Log.w(TAG, "[$TAG] GPU vision failed: ${gpuVisionErr.message}. Trying text-only fallback...")
                    }
                }

                if (!cpuEngineLoaded) {
                    try {
                        val config = EngineConfig(
                            modelPath = modelPath,
                            backend = Backend.CPU(threadCount = 4),
                            maxNumTokens = 2048,
                            cacheDir = effectiveCacheDir
                        )
                        testEngine = Engine(config)
                        testEngine.initialize()
                        loadedEngine = testEngine
                        backendChosen = BackendType.CPU
                        Log.i(TAG, "[$TAG] Model loaded successfully on CPU (text-only fallback)")
                    } catch (fatal: Throwable) {
                        try { testEngine?.close() } catch (_: Throwable) {}
                        testEngine = null
                        if (fatal is CancellationException) throw fatal
                        val fatalMsg = "Failed to load model on CPU: ${fatal.localizedMessage}"
                        Log.e(TAG, "[$TAG] $fatalMsg", fatal)
                        _engineState.value = EngineState.Error(fatalMsg)
                        return@withContext Result.failure(Exception(fatalMsg, fatal))
                    }
                }
            } else {
                // User explicitly selected GPU: try GPU with GPU vision
                var lastGpuError: String? = null
                try {
                    Log.d(TAG, "[$TAG] Attempting GPU initialization with GPU vision backend...")
                    val config = EngineConfig(
                        modelPath = modelPath,
                        backend = Backend.GPU(),
                        visionBackend = Backend.GPU(),
                        maxNumTokens = 2048,
                        maxNumImages = 1,
                        cacheDir = effectiveCacheDir
                    )
                    testEngine = Engine(config)
                    testEngine.initialize()
                    loadedEngine = testEngine
                    backendChosen = BackendType.GPU
                    Log.i(TAG, "[$TAG] Model loaded successfully on GPU with GPU vision")
                } catch (eGpu: Throwable) {
                    lastGpuError = eGpu.message ?: "GPU unsupported or out of memory"
                    Log.w(TAG, "[$TAG] GPU initialization failed: $lastGpuError. Cleaning up before CPU fallback...")
                    try { testEngine?.close() } catch (_: Throwable) {}
                    testEngine = null
                    System.gc()
                    kotlinx.coroutines.delay(300)

                    Log.i(TAG, "[$TAG] Falling back to CPU with 4 threads and CPU vision...")
                    _engineState.value = EngineState.Loading("Falling back to CPU...")

                    try {
                        val config = EngineConfig(
                            modelPath = modelPath,
                            backend = Backend.CPU(threadCount = 4),
                            visionBackend = Backend.CPU(threadCount = 4),
                            maxNumTokens = 2048,
                            maxNumImages = 1,
                            cacheDir = effectiveCacheDir
                        )
                        testEngine = Engine(config)
                        testEngine.initialize()
                        loadedEngine = testEngine
                        backendChosen = BackendType.CPU_FALLBACK
                        Log.i(TAG, "[$TAG] Model loaded successfully on CPU fallback with CPU vision")
                    } catch (fatal: Throwable) {
                        try { testEngine?.close() } catch (_: Throwable) {}
                        testEngine = null
                        System.gc()
                        if (fatal is CancellationException) throw fatal
                        val fatalMsg = "Failed to load model: GPU error: [$lastGpuError]. CPU error: [${fatal.localizedMessage}]"
                        Log.e(TAG, "[$TAG] $fatalMsg", fatal)
                        _engineState.value = EngineState.Error(fatalMsg)
                        return@withContext Result.failure(Exception(fatalMsg, fatal))
                    }
                }
            }

            // Create initial conversation session
            try {
                val nonNullEngine = loadedEngine ?: run {
                    val errorMsg = "Engine initialization failed: no backend could be loaded."
                    _engineState.value = EngineState.Error(errorMsg)
                    return@withContext Result.failure(IllegalStateException(errorMsg))
                }
                engine = nonNullEngine
                activeBackend = backendChosen
                val convConfig = buildConversationConfig(currentConfig)
                conversation = try {
                    nonNullEngine.createConversation(convConfig)
                } catch (convFallback: Throwable) {
                    Log.w(TAG, "[$TAG] Custom conversation config failed, falling back to default: ${convFallback.message}")
                    nonNullEngine.createConversation()
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

        // Ensure generation threads run with background priority so Android UI / SurfaceFlinger never lags or freezes
        try {
            android.os.Process.setThreadPriority(android.os.Process.THREAD_PRIORITY_BACKGROUND)
        } catch (_: Throwable) {}

        val eng = engine
        check(eng != null && eng.isInitialized()) { "Model is not initialized. Please install model first." }

        val effectiveSysPrompt = systemInstruction ?: currentConfig.systemPrompt
        val basePromptTokens = com.teja.gemmmobile.context.ContextManager.estimateTokens(prompt) +
            com.teja.gemmmobile.context.ContextManager.estimateTokens(effectiveSysPrompt)
        val effectiveThinking = enableThinkingOverride ?: currentConfig.enableThinking
        val effectiveThinkingBudget = if (effectiveThinking) minOf(currentConfig.thinkingBudget, 160) else 0

        val totalModelMaxContext = 2048
        val safetyMargin = 32

        try {
            var attempt = 0
            var succeeded = false
            var currentImageBytes = imageBytes?.let { com.teja.gemmmobile.storage.StorageManagerHelper.compressForVision(it) }

            while (attempt < 2 && !succeeded) {
                attempt++

                val imageTokens = if (currentImageBytes != null) 576 else 0
                val totalPromptTokens = basePromptTokens + imageTokens

                // For multimodal vision inputs, disable thinking to reserve full KV-cache for generation
                var currentThinking = if (currentImageBytes != null) false else effectiveThinking
                var currentThinkBudget = if (currentImageBytes != null) 0 else effectiveThinkingBudget

                var availableForOutput = totalModelMaxContext - totalPromptTokens - currentThinkBudget - safetyMargin
                if (availableForOutput < 64 && currentThinking) {
                    currentThinking = false
                    currentThinkBudget = 0
                    availableForOutput = totalModelMaxContext - totalPromptTokens - safetyMargin
                }

                if (availableForOutput < 32) {
                    val errorMsg = "Context budget reached ($totalPromptTokens tokens). Maximum context is $totalModelMaxContext tokens. Please start a new chat or shorten the message."
                    Log.w(TAG, "[$TAG] $errorMsg")
                    throw IllegalStateException(errorMsg)
                }

                val dynamicMaxOutput = minOf(currentConfig.maxTokens, maxOf(128, availableForOutput))
                Log.d(TAG, "[$TAG] Starting attempt $attempt with promptTokens=$totalPromptTokens, maxOutput=$dynamicMaxOutput, thinking=$currentThinking, thinkBudget=$currentThinkBudget, hasImage=${currentImageBytes != null}")

                val thinkingConfig = ThinkingConfig(
                    enableThinking = currentThinking,
                    thinkingTokenBudget = currentThinkBudget
                )

                try {
                    val targetConv = mutex.withLock {
                        // Always create a fresh, clean conversation session per turn so LiteRT-LM's
                        // native KV cache never accumulates old turns and exceeds the 4096 token limit.
                        // Context and history are managed strictly within budget by ContextManager.
                        try { conversation?.close() } catch (_: Throwable) {}
                        val cur = eng.createConversation(
                            buildConversationConfig(
                                currentConfig,
                                currentThinking,
                                dynamicMaxOutput,
                                systemInstructionText = effectiveSysPrompt
                            )
                        )
                        conversation = cur
                        _engineState.value = EngineState.Generating(activeBackend)
                        cur
                    }

                    val messageFlow = if (currentImageBytes != null && currentImageBytes.isNotEmpty()) {
                        var visionBytes = currentImageBytes
                        var visionFlow: kotlinx.coroutines.flow.Flow<Message>? = null

                        // Attempt 1: send as-is (JPEG)
                        try {
                            val contents = Contents.of(
                                Content.ImageBytes(visionBytes!!),
                                Content.Text(prompt)
                            )
                            visionFlow = targetConv.sendMessageAsync(contents = contents, thinkingConfig = thinkingConfig)
                            Log.d(TAG, "[$TAG] Vision: sending JPEG bytes (${visionBytes.size} bytes)")
                        } catch (e1: Throwable) {
                            Log.w(TAG, "[$TAG] Vision JPEG failed: ${e1.message}. Trying PNG re-encode...")
                            // Attempt 2: re-encode to PNG
                            try {
                                val bmp = android.graphics.BitmapFactory.decodeByteArray(visionBytes, 0, visionBytes!!.size)
                                if (bmp != null) {
                                    val pngStream = java.io.ByteArrayOutputStream()
                                    bmp.compress(android.graphics.Bitmap.CompressFormat.PNG, 100, pngStream)
                                    val pngBytes = pngStream.toByteArray()
                                    val contents = Contents.of(
                                        Content.ImageBytes(pngBytes),
                                        Content.Text(prompt)
                                    )
                                    visionFlow = targetConv.sendMessageAsync(contents = contents, thinkingConfig = thinkingConfig)
                                    Log.d(TAG, "[$TAG] Vision: PNG re-encode succeeded (${pngBytes.size} bytes)")
                                } else throw IllegalStateException("Bitmap decode failed")
                            } catch (e2: Throwable) {
                                Log.w(TAG, "[$TAG] Vision PNG also failed: ${e2.message}. Emitting error to user.")
                                // Both formats failed — emit clear message, don't confuse model
                                emit(EngineChunk(text = "I wasn't able to process this image. The on-device model may not support image inputs, or the image format is unsupported. Try describing what you'd like to know and I'll help with text."))
                                succeeded = true
                                currentImageBytes = null
                                break
                            }
                        }

                        visionFlow ?: targetConv.sendMessageAsync(text = prompt, thinkingConfig = thinkingConfig)
                    } else {
                        targetConv.sendMessageAsync(text = prompt, thinkingConfig = thinkingConfig)
                    }

                    var emittedAny = false
                    if (!succeeded) {
                        messageFlow.collect { message: Message ->
                            val thoughtChannel = message.channels["thought"]
                                ?: message.channels["thinking"]
                                ?: ""
                            val textContent = message.toString()

                            if (thoughtChannel.isNotEmpty() || textContent.isNotEmpty()) {
                                emittedAny = true
                                emit(EngineChunk(text = textContent, thought = thoughtChannel))
                            }
                        }
                    }

                    if (!succeeded && !emittedAny && currentImageBytes != null) {
                        // Model accepted but returned nothing — emit clear message
                        Log.w(TAG, "[$TAG] Vision input yielded 0 tokens.")
                        emit(EngineChunk(text = "I received the image but couldn't generate a response. The model may not fully support vision on this device. Please try again or describe the image in text."))
                        currentImageBytes = null
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
                    if (currentImageBytes != null && attempt < 2) {
                        Log.w(TAG, "[$TAG] Vision generation failed ($errStr), emitting error to user.")
                        emit(EngineChunk(text = "I wasn't able to analyze this image. The model may not support vision on this device. Try describing what's in the image and I'll help with text."))
                        succeeded = true
                        break
                    }
                    Log.e(TAG, "[$TAG] Generation failure", e)
                    throw e
                }
            }
        } finally {
            mutex.withLock {
                try { conversation?.close() } catch (_: Throwable) {}
                conversation = null
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
