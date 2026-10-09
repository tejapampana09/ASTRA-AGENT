package com.teja.gemmmobile.model

import android.content.Context
import android.net.Uri
import android.os.StatFs
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.withContext
import java.io.File
import java.io.FileOutputStream
import java.io.InputStream
import java.text.DecimalFormat
import com.teja.gemmmobile.ai.GemmaConfig

private const val TAG = "GemmaMobile"

/**
 * State representing the installation status of the Gemma 4 E2B IT model.
 */
sealed interface ModelInstallState {
    data object NotInstalled : ModelInstallState
    data class Checking(val message: String) : ModelInstallState
    data class Installing(val progress: Float, val transferredBytes: Long, val totalBytes: Long) : ModelInstallState
    data class Installed(val modelFile: File, val sizeBytes: Long) : ModelInstallState
    data class Error(val message: String) : ModelInstallState
}

/**
 * Manages detection, verification, storage validation, and installation
 * of the local Gemma 4 E2B IT .litertlm model file.
 */
class ModelManager(private val context: Context) {

    companion object {
        const val MODEL_FILENAME = "gemma-4-E2B-it.litertlm"
        // Gemma 4 E2B IT model is approximately 2.58 GB
        const val APPROXIMATE_MODEL_SIZE_BYTES = 2_588_147_712L // ~2.58 GB
        const val MINIMUM_FREE_STORAGE_BYTES = 3_000_000_000L // 3.0 GB safety margin

        const val HF_MODEL_URL = "https://huggingface.co/litert-community/gemma-4-E2B-it-litert-lm/resolve/main/gemma-4-E2B-it.litertlm"
        private const val PREFS_NAME = "gemma_prefs"
        private const val KEY_HF_TOKEN = "hf_token"
        const val DEFAULT_HF_TOKEN = ""
        const val MIN_VALID_MODEL_SIZE_BYTES = 1_900_000_000L // Minimum valid size (~1.9 GB; full model is 2.58 GB)
    }

    private val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    private val _installState = MutableStateFlow<ModelInstallState>(ModelInstallState.NotInstalled)
    val installState: StateFlow<ModelInstallState> = _installState.asStateFlow()

    private val modelsDir: File
        get() = File(context.filesDir, "models").apply { if (!exists()) mkdirs() }

    val defaultModelFile: File
        get() = File(modelsDir, MODEL_FILENAME)

    fun getSavedHfToken(): String {
        val saved = prefs.getString(KEY_HF_TOKEN, null)
        return if (!saved.isNullOrBlank()) saved else DEFAULT_HF_TOKEN
    }

    fun saveHfToken(token: String) {
        if (token.isNotBlank()) {
            prefs.edit().putString(KEY_HF_TOKEN, token.trim()).apply()
        }
    }

    fun loadConfig(): GemmaConfig {
        val backendStr = prefs.getString("config_preferred_backend", com.teja.gemmmobile.ai.PreferredBackend.CPU.name)
        val preferred = try {
            com.teja.gemmmobile.ai.PreferredBackend.valueOf(backendStr ?: com.teja.gemmmobile.ai.PreferredBackend.CPU.name)
        } catch (_: Exception) {
            com.teja.gemmmobile.ai.PreferredBackend.CPU
        }

        val savedPrompt = prefs.getString("config_system_prompt", null)
        val effectivePrompt = if (savedPrompt.isNullOrBlank() ||
            savedPrompt.contains("CONVERSATIONAL RESPONSE STYLE") ||
            savedPrompt.contains("LANGUAGE RULE (CRITICAL)") ||
            savedPrompt.contains("Break down key concepts or architecture using") ||
            savedPrompt.contains("Begin with a clear 1-2 sentence core overview") ||
            savedPrompt.contains("Interactive Engagement")
        ) {
            GemmaConfig.DEFAULT_SYSTEM_PROMPT
        } else {
            savedPrompt
        }

        val savedTokens = prefs.getInt("config_tokens", GemmaConfig.DEFAULT.maxTokens)
        val effectiveTokens = if (savedTokens < 1200) 1200 else savedTokens

        return GemmaConfig(
            temperature = prefs.getFloat("config_temp", 0.65f),
            maxTokens = effectiveTokens,
            topP = prefs.getFloat("config_topp", 0.90f),
            topK = prefs.getInt("config_topk", 40),
            enableThinking = prefs.getBoolean("config_thinking", false),
            thinkingBudget = prefs.getInt("config_thinking_budget", 0),
            systemPrompt = effectivePrompt,
            preferredBackend = preferred
        )
    }

    fun saveConfig(config: GemmaConfig) {
        prefs.edit()
            .putFloat("config_temp", config.temperature)
            .putInt("config_tokens", config.maxTokens)
            .putFloat("config_topp", config.topP)
            .putInt("config_topk", config.topK)
            .putBoolean("config_thinking", config.enableThinking)
            .putInt("config_thinking_budget", config.thinkingBudget)
            .putString("config_system_prompt", config.systemPrompt)
            .putString("config_preferred_backend", config.preferredBackend.name)
            .apply()
    }

    /**
     * Checks if a valid Gemma 4 E2B model exists on the device.
     * Automatically cleans up any corrupted or partially-downloaded files (< 1.9 GB).
     */
    suspend fun checkModelAvailability(): ModelInstallState = withContext(Dispatchers.IO) {
        _installState.value = ModelInstallState.Checking("Verifying model availability...")
        Log.d(TAG, "[$TAG] Checking model availability across local storage...")

        // 1. Primary app-private storage
        val internalModel = defaultModelFile
        if (internalModel.exists()) {
            if (internalModel.length() >= MIN_VALID_MODEL_SIZE_BYTES) {
                Log.d(TAG, "[$TAG] Found valid model in app-private storage: ${internalModel.absolutePath} (${formatSize(internalModel.length())})")
                val state = ModelInstallState.Installed(internalModel, internalModel.length())
                _installState.value = state
                return@withContext state
            } else {
                Log.w(TAG, "[$TAG] Detected corrupted/partial internal model (${formatSize(internalModel.length())}). Deleting to unblock fresh install...")
                try { internalModel.delete() } catch (e: Exception) { Log.w(TAG, "Failed to delete corrupted file", e) }
            }
        }

        // 2. Check external app-specific storage (/sdcard/Android/data/<package>/files/models/)
        val externalDir = context.getExternalFilesDir("models")
        if (externalDir != null) {
            val externalModel = File(externalDir, MODEL_FILENAME)
            if (externalModel.exists()) {
                if (externalModel.length() >= MIN_VALID_MODEL_SIZE_BYTES && externalModel.canRead()) {
                    Log.d(TAG, "[$TAG] Found valid model in external app storage: ${externalModel.absolutePath} (${formatSize(externalModel.length())})")
                    val state = ModelInstallState.Installed(externalModel, externalModel.length())
                    _installState.value = state
                    return@withContext state
                } else if (externalModel.length() < MIN_VALID_MODEL_SIZE_BYTES) {
                    Log.w(TAG, "[$TAG] Detected corrupted/partial external model. Deleting...")
                    try { externalModel.delete() } catch (_: Exception) {}
                }
            }
        }

        // Also check direct external package models dir
        val rawExternalDir = File("/sdcard/Android/data/${context.packageName}/files/models")
        if (rawExternalDir.exists()) {
            val candidate = File(rawExternalDir, MODEL_FILENAME)
            if (candidate.exists() && candidate.canRead() && candidate.length() >= MIN_VALID_MODEL_SIZE_BYTES) {
                Log.d(TAG, "[$TAG] Found valid model in raw external storage: ${candidate.absolutePath}")
                val state = ModelInstallState.Installed(candidate, candidate.length())
                _installState.value = state
                return@withContext state
            }
        }

        // 3. Check /data/local/tmp (ADB pushed path - directly readable by LiteRT-LM without 2.58 GB duplication!)
        val adbTempFile = File("/data/local/tmp/$MODEL_FILENAME")
        if (adbTempFile.exists() && adbTempFile.canRead() && adbTempFile.length() >= MIN_VALID_MODEL_SIZE_BYTES) {
            Log.d(TAG, "[$TAG] Found complete model in /data/local/tmp: ${adbTempFile.absolutePath} (${formatSize(adbTempFile.length())})")
            val state = ModelInstallState.Installed(adbTempFile, adbTempFile.length())
            _installState.value = state
            return@withContext state
        }

        // 4. Check common Downloads directories on device
        val downloadDirs = listOfNotNull(
            File("/sdcard/Download"),
            File("/sdcard/Download/models"),
            File("/storage/emulated/0/Download"),
            File("/storage/emulated/0/Download/models"),
            android.os.Environment.getExternalStoragePublicDirectory(android.os.Environment.DIRECTORY_DOWNLOADS)
        )
        for (dir in downloadDirs) {
            if (!dir.exists()) continue
            val candidate = File(dir, MODEL_FILENAME)
            if (candidate.exists() && candidate.canRead() && candidate.length() >= MIN_VALID_MODEL_SIZE_BYTES) {
                Log.d(TAG, "[$TAG] Found valid model in Download directory: ${candidate.absolutePath} (${formatSize(candidate.length())})")
                val state = ModelInstallState.Installed(candidate, candidate.length())
                _installState.value = state
                return@withContext state
            }

            // Also check for any .litertlm file >= 1.9 GB in Download folder
            val litertFiles = dir.listFiles { f -> f.extension.equals("litertlm", ignoreCase = true) && f.length() >= MIN_VALID_MODEL_SIZE_BYTES }
            if (!litertFiles.isNullOrEmpty()) {
                val found = litertFiles.first()
                if (found.canRead()) {
                    Log.d(TAG, "[$TAG] Found valid .litertlm model in Download directory: ${found.absolutePath} (${formatSize(found.length())})")
                    val state = ModelInstallState.Installed(found, found.length())
                    _installState.value = state
                    return@withContext state
                }
            }
        }

        Log.d(TAG, "[$TAG] Model not installed or valid model not found on device.")
        val state = ModelInstallState.NotInstalled
        _installState.value = state
        state
    }

    /**
     * Downloads the Gemma 4 E2B IT model directly from Hugging Face into app-private storage.
     * Follows HTTP 302 redirects to CDN and reports live progress.
     */
    suspend fun downloadModelFromHf(
        token: String = getSavedHfToken()
    ): Result<File> = withContext(Dispatchers.IO) {
        try {
            if (!hasSufficientStorage()) {
                val errorMsg = "Not enough internal storage. Need at least 3.0 GB free space."
                Log.e(TAG, "[$TAG] $errorMsg")
                _installState.value = ModelInstallState.Error(errorMsg)
                return@withContext Result.failure(IllegalStateException(errorMsg))
            }

            saveHfToken(token)

            val targetFile = defaultModelFile
            val tempFile = File(modelsDir, "$MODEL_FILENAME.tmp")
            if (tempFile.exists()) {
                tempFile.delete()
            }

            _installState.value = ModelInstallState.Installing(0f, 0L, APPROXIMATE_MODEL_SIZE_BYTES)
            Log.d(TAG, "[$TAG] Starting in-app direct download from $HF_MODEL_URL...")

            // Initial connection to Hugging Face
            var currentUrl = java.net.URL(HF_MODEL_URL)
            var connection = (currentUrl.openConnection() as java.net.HttpURLConnection).apply {
                connectTimeout = 30000
                readTimeout = 30000
                instanceFollowRedirects = false
                if (token.isNotBlank()) {
                    setRequestProperty("Authorization", "Bearer ${token.trim()}")
                }
                setRequestProperty("User-Agent", "GemmaMobile-Android/1.0")
            }

            var redirectCount = 0
            while (redirectCount < 5) {
                val responseCode = connection.responseCode
                Log.d(TAG, "[$TAG] HTTP $responseCode from ${currentUrl.host}")

                if (responseCode in 300..399) {
                    val location = connection.getHeaderField("Location")
                        ?: throw IllegalStateException("Redirect without Location header")
                    connection.disconnect()

                    currentUrl = java.net.URL(location)
                    connection = (currentUrl.openConnection() as java.net.HttpURLConnection).apply {
                        connectTimeout = 30000
                        readTimeout = 60000
                        instanceFollowRedirects = false
                        // Only send Authorization header to huggingface.co domains (S3 rejects Auth headers with pre-signed URLs)
                        if (token.isNotBlank() && currentUrl.host.endsWith("huggingface.co")) {
                            setRequestProperty("Authorization", "Bearer ${token.trim()}")
                        }
                        setRequestProperty("User-Agent", "GemmaMobile-Android/1.0")
                    }
                    redirectCount++
                } else if (responseCode == 200) {
                    break
                } else if (responseCode == 401 || responseCode == 403) {
                    connection.disconnect()
                    val msg = "Hugging Face authentication failed ($responseCode). Please check your HF token and ensure you have accepted the Gemma license."
                    _installState.value = ModelInstallState.Error(msg)
                    return@withContext Result.failure(IllegalStateException(msg))
                } else {
                    connection.disconnect()
                    val msg = "Download failed with HTTP error $responseCode: ${connection.responseMessage}"
                    _installState.value = ModelInstallState.Error(msg)
                    return@withContext Result.failure(IllegalStateException(msg))
                }
            }

            val totalBytes = connection.contentLengthLong.takeIf { it > 0 } ?: APPROXIMATE_MODEL_SIZE_BYTES
            Log.d(TAG, "[$TAG] Download stream opened. Total size: $totalBytes bytes (${formatSize(totalBytes)})")

            connection.inputStream.use { input ->
                FileOutputStream(tempFile).use { output ->
                    val buffer = ByteArray(256 * 1024) // 256 KB buffer for fast streaming
                    var bytesRead: Int
                    var totalTransferred = 0L
                    var lastReportTime = System.currentTimeMillis()

                    while (input.read(buffer).also { bytesRead = it } != -1) {
                        output.write(buffer, 0, bytesRead)
                        totalTransferred += bytesRead

                        val now = System.currentTimeMillis()
                        if (now - lastReportTime > 250 || totalTransferred == totalBytes) {
                            val progress = (totalTransferred.toDouble() / totalBytes.toDouble()).toFloat().coerceIn(0f, 1f)
                            _installState.value = ModelInstallState.Installing(progress, totalTransferred, totalBytes)
                            lastReportTime = now
                        }
                    }
                    output.flush()
                }
            }
            connection.disconnect()

            if (targetFile.exists()) {
                targetFile.delete()
            }
            if (!tempFile.renameTo(targetFile)) {
                tempFile.copyTo(targetFile, overwrite = true)
                tempFile.delete()
            }

            Log.d(TAG, "[$TAG] Model downloaded successfully to ${targetFile.absolutePath} (${formatSize(targetFile.length())})")
            _installState.value = ModelInstallState.Installed(targetFile, targetFile.length())
            Result.success(targetFile)
        } catch (e: Exception) {
            Log.e(TAG, "[$TAG] In-app download error", e)
            val error = "Download failed: ${e.localizedMessage ?: "Network error"}"
            _installState.value = ModelInstallState.Error(error)
            Result.failure(e)
        }
    }

    /**
     * Deletes the installed model from app-private storage.
     */
    suspend fun deleteModel(): Boolean = withContext(Dispatchers.IO) {
        val file = defaultModelFile
        val deleted = if (file.exists()) file.delete() else false
        checkModelAvailability()
        deleted
    }

    /**
     * Returns true if there is sufficient internal free storage to install the model.
     */
    fun hasSufficientStorage(): Boolean {
        return try {
            val stat = StatFs(context.filesDir.absolutePath)
            val available = stat.availableBytes
            available >= MINIMUM_FREE_STORAGE_BYTES
        } catch (e: Exception) {
            Log.e(TAG, "[$TAG] Error checking storage capacity", e)
            true
        }
    }

    fun getAvailableStorageBytes(): Long {
        return try {
            val stat = StatFs(context.filesDir.absolutePath)
            stat.availableBytes
        } catch (e: Exception) {
            -1L
        }
    }

    /**
     * Imports a user-selected .litertlm model file from a SAF Uri into app-private storage.
     */
    suspend fun importModelFromUri(uri: Uri): Result<File> = withContext(Dispatchers.IO) {
        try {
            if (!hasSufficientStorage()) {
                val errorMsg = "Not enough storage to install the model. Need at least 3.0 GB free space."
                Log.e(TAG, "[$TAG] $errorMsg")
                _installState.value = ModelInstallState.Error(errorMsg)
                return@withContext Result.failure(IllegalStateException(errorMsg))
            }

            val contentResolver = context.contentResolver
            val inputStream: InputStream = contentResolver.openInputStream(uri)
                ?: return@withContext Result.failure(IllegalStateException("Unable to open selected file"))

            val totalSize = contentResolver.openFileDescriptor(uri, "r")?.use { it.statSize } ?: -1L
            val targetFile = defaultModelFile
            val tempFile = File(modelsDir, "$MODEL_FILENAME.tmp")

            Log.d(TAG, "[$TAG] Importing model to ${tempFile.absolutePath} (total size: $totalSize bytes)...")
            _installState.value = ModelInstallState.Installing(0f, 0L, totalSize)

            inputStream.use { input ->
                FileOutputStream(tempFile).use { output ->
                    val buffer = ByteArray(1024 * 1024) // 1MB buffer
                    var bytesRead: Int
                    var totalTransferred = 0L

                    while (input.read(buffer).also { bytesRead = it } != -1) {
                        output.write(buffer, 0, bytesRead)
                        totalTransferred += bytesRead
                        val progress = if (totalSize > 0) totalTransferred.toFloat() / totalSize.toFloat() else 0.5f
                        _installState.value = ModelInstallState.Installing(progress, totalTransferred, totalSize)
                    }
                    output.flush()
                }
            }

            // Rename tmp file to target file on success
            if (targetFile.exists()) {
                targetFile.delete()
            }
            if (!tempFile.renameTo(targetFile)) {
                tempFile.copyTo(targetFile, overwrite = true)
                tempFile.delete()
            }

            Log.d(TAG, "[$TAG] Model imported successfully: ${targetFile.absolutePath} (${formatSize(targetFile.length())})")
            _installState.value = ModelInstallState.Installed(targetFile, targetFile.length())
            Result.success(targetFile)
        } catch (e: Exception) {
            Log.e(TAG, "[$TAG] Model import failed", e)
            val error = "Model import failed: ${e.localizedMessage ?: "Unknown error"}"
            _installState.value = ModelInstallState.Error(error)
            Result.failure(e)
        }
    }

    /**
     * Formats bytes into a human-readable string (e.g. 2.58 GB).
     */
    fun formatSize(bytes: Long): String {
        if (bytes <= 0) return "0 B"
        val units = arrayOf("B", "KB", "MB", "GB", "TB")
        val digitGroups = (Math.log10(bytes.toDouble()) / Math.log10(1024.0)).toInt()
        val format = DecimalFormat("#,##0.##")
        return "${format.format(bytes / Math.pow(1024.0, digitGroups.toDouble()))} ${units[digitGroups]}"
    }
}
