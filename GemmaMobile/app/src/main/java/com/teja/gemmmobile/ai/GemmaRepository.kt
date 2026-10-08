package com.teja.gemmmobile.ai

import android.content.Context
import android.util.Log
import com.teja.gemmmobile.model.ModelInstallState
import com.teja.gemmmobile.model.ModelManager
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import java.io.File

private const val TAG = "GemmaRepository"

/**
 * Global singleton repository holding the active on-device GemmaEngine instance.
 * Shares the single 2.58 GB loaded model between MainActivity and AssistantActivity,
 * ensuring instant switching, zero duplicate memory usage, and unified state.
 */
object GemmaRepository {

    private val repositoryScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val mutex = Mutex()

    private var activeEngine: GemmaEngine? = null
    private var engineStateJob: Job? = null

    private val _engineState = MutableStateFlow<EngineState>(EngineState.Uninitialized)
    val engineState: StateFlow<EngineState> = _engineState.asStateFlow()

    private val _lastError = MutableStateFlow<String?>(null)
    val lastError: StateFlow<String?> = _lastError.asStateFlow()

    fun getEngine(): GemmaEngine? = activeEngine

    fun isReady(): Boolean = _engineState.value is EngineState.Ready

    fun resetToReady() {
        activeEngine?.resetToReady()
        val backend = (activeEngine?.engineState?.value as? EngineState.Ready)?.backend ?: BackendType.GPU
        _engineState.value = EngineState.Ready(backend)
    }

    /**
     * Retrieves the existing engine if ready, or initializes it if a valid model file is found.
     */
    suspend fun getOrInitializeEngine(context: Context, customConfig: GemmaConfig? = null): GemmaEngine? = withContext(Dispatchers.IO) {
        mutex.withLock {
            if (activeEngine != null && _engineState.value is EngineState.Ready) {
                return@withContext activeEngine
            }

            val modelManager = ModelManager(context.applicationContext)
            val config = customConfig ?: modelManager.loadConfig()
            val installState = modelManager.checkModelAvailability()
            val modelFile = (installState as? ModelInstallState.Installed)?.modelFile ?: modelManager.defaultModelFile

            if (!modelFile.exists() || modelFile.length() < 1_000_000L) {
                _lastError.value = "Gemma model is not installed."
                return@withContext null
            }

            val cacheDir = context.cacheDir.absolutePath
            return@withContext initEngineInternal(modelFile, config, cacheDir)
        }
    }

    suspend fun reinitializeEngine(
        modelFile: File,
        config: GemmaConfig,
        cacheDir: String? = null
    ): Result<BackendType> = withContext(Dispatchers.IO) {
        mutex.withLock {
            _lastError.value = null
            activeEngine?.close()
            activeEngine = null
            engineStateJob?.cancel()

            val engine = initEngineInternal(modelFile, config, cacheDir)
            if (engine != null) {
                val backend = (engine.engineState.value as? EngineState.Ready)?.backend ?: BackendType.GPU
                _engineState.value = EngineState.Ready(backend)
                _lastError.value = null
                Result.success(backend)
            } else {
                val err = _lastError.value ?: "Model initialization failed. Please verify that the 2.58 GB model is completely downloaded."
                _engineState.value = EngineState.Error(err)
                Result.failure(Exception(err))
            }
        }
    }

    private suspend fun initEngineInternal(
        modelFile: File,
        config: GemmaConfig,
        cacheDir: String? = null
    ): GemmaEngine? {
        _engineState.value = EngineState.Loading("Initializing Gemma...")
        try {
            val resolvedCacheDir = cacheDir ?: File(modelFile.parentFile ?: File("."), "litert_cache").apply { mkdirs() }.absolutePath
            val newEngine = GemmaEngine(modelFile.absolutePath, config, resolvedCacheDir)
            engineStateJob?.cancel()
            engineStateJob = repositoryScope.launch {
                newEngine.engineState.collect { state ->
                    _engineState.value = state
                    if (state is EngineState.Error) {
                        _lastError.value = state.message
                    }
                }
            }

            val result = newEngine.initialize()
            return if (result.isSuccess) {
                activeEngine = newEngine
                val backend = result.getOrNull() ?: BackendType.GPU
                _engineState.value = EngineState.Ready(backend)
                _lastError.value = null
                newEngine
            } else {
                val err = result.exceptionOrNull()?.localizedMessage
                    ?: result.exceptionOrNull()?.message
                    ?: "Failed to initialize engine"
                _lastError.value = err
                _engineState.value = EngineState.Error(err)
                try { newEngine.close() } catch (_: Throwable) {}
                null
            }
        } catch (t: Throwable) {
            val err = t.localizedMessage ?: t.message ?: "Failed to initialize engine"
            _lastError.value = err
            _engineState.value = EngineState.Error(err)
            return null
        }
    }

    suspend fun updateConfig(config: GemmaConfig) = withContext(Dispatchers.IO) {
        activeEngine?.updateConfig(config)
    }

    fun close() {
        repositoryScope.launch {
            mutex.withLock {
                engineStateJob?.cancel()
                activeEngine?.close()
                activeEngine = null
                _engineState.value = EngineState.Uninitialized
            }
        }
    }
}
