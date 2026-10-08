package com.teja.gemmmobile.ui

import android.app.Application
import android.content.Context
import android.net.Uri
import android.os.PowerManager
import android.util.Log
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.teja.gemmmobile.ai.BackendType
import com.teja.gemmmobile.ai.EngineState
import com.teja.gemmmobile.ai.GemmaConfig
import com.teja.gemmmobile.ai.GemmaEngine
import com.teja.gemmmobile.ai.GemmaRepository
import com.teja.gemmmobile.model.ModelInstallState
import com.teja.gemmmobile.model.ModelManager
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.launch
import com.teja.gemmmobile.memory.MemoryItem
import com.teja.gemmmobile.memory.MemoryManager
import com.teja.gemmmobile.search.SearchResult
import com.teja.gemmmobile.search.SearchImage
import com.teja.gemmmobile.search.WebSearchClient
import com.teja.gemmmobile.audio.TtsManager
import com.teja.gemmmobile.ocr.ExtractedDocument
import com.teja.gemmmobile.storage.ChatSession
import com.teja.gemmmobile.storage.ChatStorage
import android.graphics.Bitmap
import java.util.UUID

private const val TAG = "GemmaMobile"

enum class MessageRole {
    USER,
    ASSISTANT
}

@androidx.compose.runtime.Immutable
data class ChatMessage(
    val id: String = UUID.randomUUID().toString(),
    val role: MessageRole,
    val text: String,
    val thoughtText: String = "",
    val searchResults: List<SearchResult> = emptyList(),
    val searchImages: List<SearchImage> = emptyList(),
    val isStreaming: Boolean = false,
    val isThinking: Boolean = false,
    val isSearchingWeb: Boolean = false,
    val isImageAnalysis: Boolean = false,
    @Transient val imageBitmap: Bitmap? = null,
    val imagePath: String? = null,
    val isExecutingTool: Boolean = false,
    val toolExecutionStatus: String? = null
)

class ChatViewModel(application: Application) : AndroidViewModel(application) {

    val modelManager = ModelManager(application.applicationContext)
    private val chatStorage = ChatStorage(application.applicationContext)
    private val searchManager = com.teja.gemmmobile.search.SearchManager()
    val memoryManager = MemoryManager(application.applicationContext)
    val toolRegistry = com.teja.gemmmobile.tools.ToolRegistry().apply {
        register(com.teja.gemmmobile.tools.WebSearchTool(searchManager))
        register(com.teja.gemmmobile.tools.ImageSearchTool(searchManager))
        register(com.teja.gemmmobile.tools.MemoryTool(memoryManager))
        register(com.teja.gemmmobile.tools.OcrTool(application.applicationContext))
    }
    val contextManager = com.teja.gemmmobile.context.ContextManager()
    private val engine: GemmaEngine? get() = GemmaRepository.getEngine()

    val installState: StateFlow<ModelInstallState> = modelManager.installState

    private val _engineState = MutableStateFlow<EngineState>(GemmaRepository.engineState.value)
    val engineState: StateFlow<EngineState> = _engineState.asStateFlow()

    private val _messages = MutableStateFlow<List<ChatMessage>>(emptyList())
    val messages: StateFlow<List<ChatMessage>> = _messages.asStateFlow()

    private val _sessions = MutableStateFlow<List<ChatSession>>(emptyList())
    val sessions: StateFlow<List<ChatSession>> = _sessions.asStateFlow()

    private val _currentSessionId = MutableStateFlow<String>(UUID.randomUUID().toString())
    val currentSessionId: StateFlow<String> = _currentSessionId.asStateFlow()

    val memories: StateFlow<List<MemoryItem>> = memoryManager.memories

    private val _inputText = MutableStateFlow("")
    val inputText: StateFlow<String> = _inputText.asStateFlow()

    private val _isGenerating = MutableStateFlow(false)
    val isGenerating: StateFlow<Boolean> = _isGenerating.asStateFlow()

    private val _isWebSearchEnabled = MutableStateFlow(false)
    val isWebSearchEnabled: StateFlow<Boolean> = _isWebSearchEnabled.asStateFlow()

    private val ttsManager = TtsManager(application)
    val isSpeaking: StateFlow<Boolean> = ttsManager.isSpeaking
    val currentlySpeakingId: StateFlow<String?> = ttsManager.currentMessageId

    private val _attachedDocument = MutableStateFlow<ExtractedDocument?>(null)
    val attachedDocument: StateFlow<ExtractedDocument?> = _attachedDocument.asStateFlow()

    private val _recentFiles = MutableStateFlow<List<ExtractedDocument>>(emptyList())
    val recentFiles: StateFlow<List<ExtractedDocument>> = _recentFiles.asStateFlow()

    private val _errorMessage = MutableStateFlow<String?>(null)
    val errorMessage: StateFlow<String?> = _errorMessage.asStateFlow()

    private val applicationScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var activeGenerationJob: Job? = null
    val activeGeneratingSessionId = MutableStateFlow<String?>(null)



    fun sendMessageWithText(text: String) {
        _inputText.value = text
        sendMessage()
    }

    private val _hfToken = MutableStateFlow(modelManager.getSavedHfToken())
    val hfToken: StateFlow<String> = _hfToken.asStateFlow()

    private val _config = MutableStateFlow(modelManager.loadConfig())
    val config: StateFlow<GemmaConfig> = _config.asStateFlow()

    private var activeDownloadJob: Job? = null

    init {
        checkModel()
        loadPersistedSessions()
        // Mirror shared engine state across entire app
        viewModelScope.launch {
            GemmaRepository.engineState.collect { state ->
                _engineState.value = state
                if (state is EngineState.Error) {
                    _errorMessage.value = state.message
                } else if (state is EngineState.Ready) {
                    _errorMessage.value = null
                }
            }
        }
        // Auto-start engine only when model becomes available in local storage
        viewModelScope.launch {
            installState.collect { state ->
                if (state is ModelInstallState.Installed && !GemmaRepository.isReady()) {
                    initializeEngine()
                }
            }
        }
    }

    private fun loadPersistedSessions() {
        viewModelScope.launch {
            val loaded = chatStorage.loadSessions()
            _sessions.value = loaded
            if (loaded.isNotEmpty()) {
                val latest = loaded.first()
                _currentSessionId.value = latest.id
                _messages.value = latest.messages
            }
        }
    }

    fun updateSessionMessages(
        sessionId: String,
        transform: (List<ChatMessage>) -> List<ChatMessage>
    ) {
        // 1. Compute updated messages from the most current source
        val baseMessages = if (_currentSessionId.value == sessionId && _messages.value.isNotEmpty()) {
            _messages.value
        } else {
            _sessions.value.find { it.id == sessionId }?.messages ?: emptyList()
        }
        val updatedMessages = transform(baseMessages)

        // 2. Update the displayed messages immediately — this is the source of truth for UI
        if (_currentSessionId.value == sessionId) {
            _messages.value = updatedMessages
        }

        // 3. Update the sessions list (find/create session, update messages, keep order stable)
        val sessionList = _sessions.value.toMutableList()
        val index = sessionList.indexOfFirst { it.id == sessionId }
        val oldSession = if (index != -1) sessionList[index] else {
            ChatSession(id = sessionId, title = "New Chat", messages = emptyList())
        }

        val title = if (oldSession.title != "New Chat") oldSession.title else {
            val firstUser = updatedMessages.firstOrNull { it.role == MessageRole.USER }?.text?.trim()
            if (!firstUser.isNullOrBlank()) firstUser.take(35) else "New Chat"
        }

        val updatedSession = oldSession.copy(
            title = title,
            updatedAt = System.currentTimeMillis(),
            messages = updatedMessages
        )

        if (index != -1) {
            sessionList[index] = updatedSession
        } else {
            sessionList.add(0, updatedSession)
        }
        // Only sort sessions in the sidebar — do not trigger a _messages reset here
        _sessions.value = sessionList.sortedByDescending { it.updatedAt }
    }

    fun persistChat() {
        val msgs = _messages.value
        if (msgs.isEmpty()) return
        val currId = _currentSessionId.value
        val existingSession = _sessions.value.find { it.id == currId }
        val title = if (existingSession != null && existingSession.title != "New Chat") {
            existingSession.title
        } else {
            val firstUser = msgs.firstOrNull { it.role == MessageRole.USER }?.text?.trim()
            if (!firstUser.isNullOrBlank()) {
                firstUser.take(35)
            } else "New Chat"
        }

        val updatedSession = ChatSession(
            id = currId,
            title = title,
            createdAt = existingSession?.createdAt ?: System.currentTimeMillis(),
            updatedAt = System.currentTimeMillis(),
            messages = msgs
        )

        val updatedList = _sessions.value.toMutableList()
        val idx = updatedList.indexOfFirst { it.id == currId }
        if (idx != -1) {
            updatedList[idx] = updatedSession
        } else {
            updatedList.add(0, updatedSession)
        }
        val sorted = updatedList.sortedByDescending { it.updatedAt }
        _sessions.value = sorted

        viewModelScope.launch {
            chatStorage.saveSession(updatedSession)
        }
    }

    fun onHfTokenChanged(token: String) {
        _hfToken.value = token
        modelManager.saveHfToken(token)
    }

    fun updateConfig(newConfig: GemmaConfig) {
        _config.value = newConfig
        modelManager.saveConfig(newConfig)
        viewModelScope.launch {
            GemmaRepository.updateConfig(newConfig)
        }
    }

    fun resetConfig() {
        updateConfig(GemmaConfig.DEFAULT)
    }

    fun checkModel() {
        viewModelScope.launch {
            modelManager.checkModelAvailability()
        }
    }

    fun downloadModel() {
        activeDownloadJob?.cancel()
        activeDownloadJob = viewModelScope.launch {
            val result = modelManager.downloadModelFromHf(_hfToken.value)
            if (result.isFailure) {
                _errorMessage.value = result.exceptionOrNull()?.localizedMessage ?: "Failed to download model"
            }
        }
    }

    fun cancelDownload() {
        activeDownloadJob?.cancel()
        activeDownloadJob = null
        checkModel()
    }

    fun deleteModel() {
        viewModelScope.launch {
            GemmaRepository.close()
            modelManager.deleteModel()
        }
    }

    fun importModel(uri: Uri) {
        viewModelScope.launch {
            val result = modelManager.importModelFromUri(uri)
            if (result.isFailure) {
                _errorMessage.value = result.exceptionOrNull()?.localizedMessage ?: "Failed to import model"
            }
        }
    }

    fun initializeEngine() {
        val currentInstallState = installState.value
        val modelFile = (currentInstallState as? ModelInstallState.Installed)?.modelFile
            ?: modelManager.defaultModelFile

        if (!modelFile.exists()) {
            _errorMessage.value = "Gemma model is not installed."
            return
        }

        viewModelScope.launch {
            val cacheDir = getApplication<Application>().cacheDir.absolutePath
            val result = GemmaRepository.reinitializeEngine(modelFile, _config.value, cacheDir)
            if (result.isFailure) {
                val err = result.exceptionOrNull()?.localizedMessage ?: "Model loading failure"
                _errorMessage.value = err
            } else {
                _errorMessage.value = null
            }
        }
    }

    fun addMemory(fact: String) {
        viewModelScope.launch {
            memoryManager.addMemory(fact)
        }
    }

    fun removeMemory(id: String) {
        viewModelScope.launch {
            memoryManager.removeMemory(id)
        }
    }

    fun clearMemories() {
        viewModelScope.launch {
            memoryManager.clearAll()
        }
    }

    fun toggleWebSearch() {
        _isWebSearchEnabled.value = !_isWebSearchEnabled.value
    }

    fun stopGeneration() {
        val genSessionId = activeGeneratingSessionId.value ?: _currentSessionId.value
        activeGenerationJob?.cancel()
        activeGenerationJob = null
        activeGeneratingSessionId.value = null
        _isGenerating.value = false

        // Force reset engine state back to Ready immediately so the badge changes
        GemmaRepository.resetToReady()
        val backend = (_engineState.value as? EngineState.Generating)?.backend ?: BackendType.GPU
        _engineState.value = EngineState.Ready(backend)

        updateSessionMessages(genSessionId) { msgs ->
            msgs.map { msg ->
                if (msg.isStreaming || msg.isThinking || msg.isSearchingWeb) {
                    msg.copy(isStreaming = false, isThinking = false, isSearchingWeb = false)
                } else msg
            }
        }
        val targetSession = _sessions.value.find { it.id == genSessionId }
        if (targetSession != null) {
            applicationScope.launch { chatStorage.saveSession(targetSession) }
        }
    }

    private fun extractSearchQuery(raw: String): String {
        return searchManager.sanitizeQuery(raw)
    }

    private fun shouldAutoSearch(prompt: String): Boolean {
        val p = prompt.lowercase().trim()

        // 1. Explicit search command from user
        if (p.startsWith("search ") || p.startsWith("web search ") || p.startsWith("browse ") ||
            p.contains("search web") || p.contains("search the web") || p.contains("search for ") ||
            p.contains("google ")) {
            return true
        }

        // 2. Real-time / live events that an LLM cannot know without search
        val realTimeKeywords = listOf(
            "latest news", "today news", "breaking news",
            "current price", "stock price", "crypto price", "live score", "match score",
            "today weather", "current weather", "weather forecast",
            "live update", "live updates", "election result",
            "login portal", "admission cutoff", "hall ticket download"
        )
        return realTimeKeywords.any { keyword -> p.contains(keyword) }
    }

    fun shouldQueryImages(prompt: String): Boolean {
        val p = prompt.lowercase().trim()
        val visualKeywords = listOf(
            "image", "images", "photo", "photos", "picture", "pictures", "pic", "pics",
            "diagram", "diagrams", "figure", "figures", "chart", "charts", "illustration",
            "wallpaper", "wallpapers", "look like", "how does it look", "visualize", "visual",
            "show me", "chupinchu", "chudu", "bomma", "bommalu"
        )
        return visualKeywords.any { keyword -> p.contains(keyword) }
    }

    fun onInputTextChanged(text: String) {
        _inputText.value = text
    }

    fun attachDocument(document: ExtractedDocument) {
        _attachedDocument.value = document
        _recentFiles.value = (listOf(document) + _recentFiles.value.filter { it.fileName != document.fileName }).take(10)
    }

    fun clearAttachedDocument() {
        _attachedDocument.value = null
    }

    fun toggleSpeak(messageId: String, text: String) {
        ttsManager.speak(messageId, text)
    }

    fun stopSpeaking() {
        ttsManager.stop()
    }

    fun getCurrentSession(): ChatSession? {
        return _sessions.value.find { it.id == _currentSessionId.value }
    }

    fun sendMessage() {
        val rawInput = _inputText.value.trim()
        val doc = _attachedDocument.value

        if (rawInput.isEmpty() && doc == null) return
        if (_isGenerating.value) return

        // Clear input text and attached document immediately
        _inputText.value = ""
        _attachedDocument.value = null

        ttsManager.stop()

        val eng = engine
        if (eng == null || _engineState.value !is EngineState.Ready) {
            _errorMessage.value = "Please wait for Gemma 4 to finish loading before sending."
            return
        }

        // Automatic memory detection: if user says "remember that..." or "remember:..."
        val lowerPrompt = rawInput.lowercase()
        if (lowerPrompt.startsWith("remember:") || lowerPrompt.startsWith("remember that ") || lowerPrompt.startsWith("remember my ") || lowerPrompt.startsWith("remember ")) {
            val factToSave = rawInput.substringAfter("remember:").substringAfter("remember that ").substringAfter("remember ").trim()
            if (factToSave.isNotBlank()) {
                viewModelScope.launch { memoryManager.addMemory(factToSave) }
            }
        }

        val imageBytesToSend = if (doc != null && doc.isImage) doc.imageBytes else null

        val isImage = doc != null && doc.isImage
        val promptForGemma = when {
            isImage -> {
                if (rawInput.isBlank()) {
                    "Examine this image in full detail. Transcribe and extract all visible text, numbers, headings, tables, labels, or data exactly as shown. If tabular data is present, format it into clean Markdown tables with column headers. Answer clearly, accurately, and thoroughly."
                } else {
                    rawInput
                }
            }
            doc != null -> {
                val userQuery = if (rawInput.isBlank()) "Please analyze, summarize, and highlight the key points of this document." else rawInput
                """
                [Attached Document: ${doc.fileName}]
                Extracted Content:
                ${doc.text}

                User Request:
                $userQuery
                """.trimIndent()
            }
            else -> rawInput
        }

        val userBubbleText = when {
            isImage -> rawInput.trim() // Clean: NO forced predefined text in user chat bubble!
            doc != null -> {
                if (rawInput.isNotBlank()) "📄 **[${doc.fileName}]**\n\n$rawInput" else "📄 **[${doc.fileName}]**"
            }
            else -> rawInput
        }

        // Web search: enable if manual toggle is on OR if prompt asks for web search / current info like ChatGPT
        val useWebSearch = (_isWebSearchEnabled.value || shouldAutoSearch(rawInput)) && !isImage

        _attachedDocument.value = null
        val userMessageId = UUID.randomUUID().toString()
        val savedImagePath = if (isImage && doc.imageBytes != null) {
            try {
                val dir = java.io.File(getApplication<Application>().filesDir, "chat_images").apply { mkdirs() }
                val imgFile = java.io.File(dir, "${userMessageId}.jpg")
                imgFile.writeBytes(doc.imageBytes)
                imgFile.absolutePath
            } catch (e: Exception) {
                Log.w(TAG, "[$TAG] Failed to save image locally", e)
                null
            }
        } else null

        val userMessage = ChatMessage(
            id = userMessageId,
            role = MessageRole.USER,
            text = userBubbleText,
            imageBitmap = if (isImage) doc.previewBitmap else null,
            imagePath = savedImagePath,
            isImageAnalysis = isImage
        )
        val assistantMessageId = UUID.randomUUID().toString()
        val initialAssistantMessage = ChatMessage(
            id = assistantMessageId,
            role = MessageRole.ASSISTANT,
            text = "",
            thoughtText = "",
            isStreaming = true,
            isThinking = _config.value.enableThinking && !useWebSearch,
            isSearchingWeb = useWebSearch,
            isImageAnalysis = isImage
        )

        val currSessionId = _currentSessionId.value
        // If a generation is running for a different session, stop it so the model can process the new request
        if (activeGeneratingSessionId.value != null && activeGeneratingSessionId.value != currSessionId) {
            stopGeneration()
        }

        updateSessionMessages(currSessionId) { msgs ->
            msgs + userMessage + initialAssistantMessage
        }

        startGeneration(
            targetSessionId = currSessionId,
            prompt = promptForGemma,
            assistantMessageId = assistantMessageId,
            eng = eng,
            useWebSearch = useWebSearch,
            allowFallback = !useWebSearch,
            imageBytes = imageBytesToSend
        )
    }



    private fun startGeneration(
        targetSessionId: String,
        prompt: String,
        assistantMessageId: String,
        eng: GemmaEngine,
        useWebSearch: Boolean,
        allowFallback: Boolean,
        imageBytes: ByteArray? = null
    ) {
        activeGenerationJob?.cancel()
        activeGeneratingSessionId.value = targetSessionId
        _isGenerating.value = (_currentSessionId.value == targetSessionId)

        activeGenerationJob = applicationScope.launch {
            val pm = getApplication<Application>().getSystemService(Context.POWER_SERVICE) as? PowerManager
            val wakeLock = pm?.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "GemmaMobile:ResponseGeneration")
            try {
                wakeLock?.acquire(5 * 60 * 1000L) // 5 minutes max wake lock
            } catch (e: Exception) {
                Log.w(TAG, "[$TAG] Could not acquire WakeLock", e)
            }

            try {
                var searchResults: List<SearchResult> = emptyList()
                var searchImages: List<SearchImage> = emptyList()
                var searchContext = ""

                if (useWebSearch) {
                    // Update searching state for this target session
                    updateSessionMessages(targetSessionId) { msgs ->
                        msgs.map { msg ->
                            if (msg.id == assistantMessageId) msg.copy(isSearchingWeb = true) else msg
                        }
                    }

                    try {
                        val cleanQuery = extractSearchQuery(prompt)
                        val enrichedResults = kotlinx.coroutines.withTimeoutOrNull(10000L) {
                            searchManager.searchAndRead(cleanQuery, maxResults = 5)
                        }
                        if (!enrichedResults.isNullOrEmpty()) {
                            searchResults = enrichedResults.map { it.toSearchResult() }
                            searchContext = searchManager.formatGemmaWebContext(enrichedResults)
                            // Image search is strictly distinct from web search: only query images when user requests visual media
                            if (shouldQueryImages(prompt)) {
                                try {
                                    searchImages = kotlinx.coroutines.withTimeoutOrNull(6000L) {
                                        searchManager.searchImages(cleanQuery, enrichedResults, maxImages = 6)
                                    } ?: emptyList()
                                } catch (e: Exception) {
                                    Log.w(TAG, "[$TAG] Image search failed", e)
                                }
                            }
                        }
                    } catch (t: Throwable) {
                        Log.w(TAG, "[$TAG] Web search failed", t)
                    } finally {
                        updateSessionMessages(targetSessionId) { msgs ->
                            msgs.map { msg ->
                                if (msg.id == assistantMessageId) msg.copy(
                                    searchResults = searchResults,
                                    searchImages = searchImages,
                                    isSearchingWeb = false
                                ) else msg
                            }
                        }
                    }
                }

                // Retrieve persistent memories and history using ContextManager
                val memoryContext = memoryManager.getFormattedMemoryPrompt()
                val sessionSnapshot = _sessions.value.find { it.id == targetSessionId }
                val targetMsgs = sessionSnapshot?.messages ?: _messages.value

                val baseSystemPrompt = _config.value.systemPrompt.ifBlank { GemmaConfig.DEFAULT_SYSTEM_PROMPT }
                val effectiveSystemPrompt = if (searchContext.isNotBlank()) {
                    """
$baseSystemPrompt

## WEB SEARCH MODE
You are provided with real-time web search results and extracted webpage content. Use them as your primary source of truth.

### RULES & GROUNDING:
1. **Lead with the direct answer** — give the most important fact or answer in the first 1-2 sentences.
2. **Ground strictly on evidence** — prefer facts supported by the extracted webpage content. If sources disagree, explicitly state the disagreement.
3. **Cite source URLs** — mention the source names and reference URLs provided in the results. Do NOT invent URLs or links not present in the sources.
4. **Dates and Recency** — for "latest/current/today" queries, prioritize recent updates found in the sources. If the fetched content is insufficient, say so instead of hallucinating.
5. **Structure clearly** — use ## headings, bullet points, bold text, and tables where useful.
6. **Language** — reply in the SAME language as the user's question (e.g. English, Telugu).

### FORMATTING BY QUERY TYPE:
- **News / Events**: Headline summary → Key details (who, what, when, where) → Impact/context
- **How-to / Tutorial**: Numbered steps → Code block if applicable → Tips
- **Comparison / "vs"**: Markdown table with pros/cons or key differences
- **Person / Entity**: Name, Role, Key facts → Recent updates
- **Price / Score / Stats**: State the exact figure first, then explain context
- **General knowledge**: Direct answer → Explanation → Follow-up suggestions
                    """.trimIndent()
                } else {
                    baseSystemPrompt
                }

                val effectivePrompt = if (imageBytes != null) {
                    prompt
                } else {
                    val historyTurns = targetMsgs.filter { it.id != assistantMessageId }.dropLast(1)
                    contextManager.buildPrompt(
                        systemPrompt = "", // Handled natively in ConversationConfig
                        toolsDocumentation = if (useWebSearch) "" else toolRegistry.getToolsDocumentation(),
                        memoryContext = memoryContext,
                        conversationHistory = historyTurns,
                        currentPrompt = prompt,
                        searchContext = searchContext
                    )
                }

                val responseBuilder = StringBuilder()
                val thoughtBuilder = StringBuilder()
                var lastUiUpdateTime = 0L
                val UI_THROTTLE_MS = 100L // 10 updates/sec: smooth fluid streaming while freeing CPU cycles

                eng.sendMessage(
                    prompt = effectivePrompt,
                    systemInstruction = effectiveSystemPrompt,
                    imageBytes = imageBytes,
                    enableThinkingOverride = if (useWebSearch) false else null
                )
                    .catch { error ->
                        Log.e(TAG, "[$TAG] Stream error", error)
                        _errorMessage.value = "Generation failure: ${error.localizedMessage ?: "Unknown error"}"
                        updateSessionMessages(targetSessionId) { msgs ->
                            msgs.map { msg ->
                                if (msg.id == assistantMessageId) {
                                    msg.copy(
                                        text = if (responseBuilder.isEmpty() && thoughtBuilder.isEmpty()) "Error: Failed to generate response." else responseBuilder.toString(),
                                        thoughtText = thoughtBuilder.toString(),
                                        isStreaming = false,
                                        isThinking = false,
                                        isSearchingWeb = false
                                    )
                                } else msg
                            }
                        }
                    }
                    .collect { chunk ->
                        if (chunk.thought.isNotEmpty()) {
                            thoughtBuilder.append(chunk.thought)
                        }

                        val chunkText = chunk.text
                        if (chunkText.isNotEmpty()) {
                            val cleanChunk = chunkText.replace("<thought>", "").replace("</thought>", "")
                            if (cleanChunk.isNotEmpty()) {
                                responseBuilder.append(cleanChunk)
                            }
                        }

                        val now = System.currentTimeMillis()
                        // Throttle UI recompositions to avoid pegging the Main thread on every token
                        if (now - lastUiUpdateTime >= UI_THROTTLE_MS) {
                            lastUiUpdateTime = now
                            val currentText = responseBuilder.toString()
                            val currentThought = thoughtBuilder.toString()
                            val stillThinking = currentText.isEmpty() && currentThought.isNotEmpty()

                            if (_currentSessionId.value == targetSessionId) {
                                _messages.value = _messages.value.map { msg ->
                                    if (msg.id == assistantMessageId) {
                                        msg.copy(
                                            text = currentText,
                                            thoughtText = currentThought,
                                            isStreaming = true,
                                            isThinking = stillThinking,
                                            isSearchingWeb = false
                                        )
                                    } else msg
                                }
                            }
                        }
                    }

                val rawFinalText = responseBuilder.toString()
                val finalThought = thoughtBuilder.toString()

                // Bounded autonomous on-device tool calling loop (up to MAX_TOOL_STEPS)
                val MAX_TOOL_STEPS = com.teja.gemmmobile.search.SearchConfig.MAX_TOOL_STEPS
                var currentToolStep = 0
                var currentGenerationText = responseBuilder.toString()
                val accumulatedToolResults = StringBuilder()
                val calledToolsHistory = mutableListOf<com.teja.gemmmobile.tools.ToolCallRequest>()
                var currentSearchImages = emptyList<SearchImage>()

                while (imageBytes == null && !useWebSearch && currentToolStep < MAX_TOOL_STEPS) {
                    val detectedToolCall = toolRegistry.parseToolCall(currentGenerationText) ?: break

                    // Duplicate tool-call and infinite loop protection
                    if (toolRegistry.isDuplicateOrLoop(calledToolsHistory, detectedToolCall)) {
                        Log.w(TAG, "[$TAG] Loop/duplicate detected for tool '${detectedToolCall.name}'. Breaking tool loop.")
                        break
                    }
                    calledToolsHistory.add(detectedToolCall)

                    currentToolStep++
                    Log.d(TAG, "[$TAG] Step $currentToolStep: Tool call detected: ${detectedToolCall.name} with ${detectedToolCall.arguments}")

                    updateSessionMessages(targetSessionId) { msgs ->
                        msgs.map { msg ->
                            if (msg.id == assistantMessageId) {
                                msg.copy(
                                    isExecutingTool = true,
                                    toolExecutionStatus = "Using ${detectedToolCall.name}...",
                                    isStreaming = false
                                )
                            } else msg
                        }
                    }

                    val toolResult = toolRegistry.execute(detectedToolCall.name, detectedToolCall.arguments)
                    accumulatedToolResults.appendLine("[Tool: ${detectedToolCall.name}]\n${toolResult.content}\n")

                    if (detectedToolCall.name == "web_search" && toolResult.data is List<*>) {
                        val newSearchResults = toolResult.data.filterIsInstance<SearchResult>()
                        if (newSearchResults.isNotEmpty()) {
                            searchResults = newSearchResults
                        }
                    } else if (detectedToolCall.name == "image_search" && toolResult.data is List<*>) {
                        val newImages = toolResult.data.filterIsInstance<SearchImage>()
                        if (newImages.isNotEmpty()) {
                            currentSearchImages = newImages
                        }
                    }

                    // Feed tool result back to the model as evidence (NOT in system prompt to prevent prompt injection)
                    val nextTurnPrompt = contextManager.buildPrompt(
                        systemPrompt = "You are a helpful, accurate AI assistant. Use the tool results below as factual evidence to answer the user's request. If more information is needed, call another tool; otherwise provide a final, comprehensive conversational answer.",
                        toolsDocumentation = if (currentToolStep < MAX_TOOL_STEPS) toolRegistry.getToolsDocumentation() else "",
                        memoryContext = memoryContext,
                        conversationHistory = targetMsgs.filter { it.id != assistantMessageId },
                        currentPrompt = prompt,
                        toolResultsContext = accumulatedToolResults.toString()
                    )

                    val nextTurnBuilder = StringBuilder()
                    updateSessionMessages(targetSessionId) { msgs ->
                        msgs.map { msg ->
                            if (msg.id == assistantMessageId) {
                                msg.copy(
                                    searchResults = searchResults,
                                    searchImages = if (currentSearchImages.isNotEmpty()) currentSearchImages else msg.searchImages,
                                    isExecutingTool = false,
                                    toolExecutionStatus = null,
                                    isStreaming = true
                                )
                            } else msg
                        }
                    }

                    try {
                        eng.sendMessage(prompt = nextTurnPrompt).collect { chunk ->
                            if (chunk.thought.isNotEmpty()) thoughtBuilder.append(chunk.thought)
                            val clean = chunk.text.replace("<thought>", "").replace("</thought>", "")
                            if (clean.isNotEmpty()) {
                                nextTurnBuilder.append(clean)
                                if (_currentSessionId.value == targetSessionId) {
                                    _messages.value = _messages.value.map { msg ->
                                        if (msg.id == assistantMessageId) {
                                            msg.copy(text = nextTurnBuilder.toString(), isStreaming = true)
                                        } else msg
                                    }
                                }
                            }
                        }
                    } catch (t: Throwable) {
                        Log.w(TAG, "[$TAG] Follow-up tool synthesis error at step $currentToolStep", t)
                    }

                    currentGenerationText = nextTurnBuilder.toString()
                    if (currentGenerationText.isNotBlank()) {
                        responseBuilder.clear()
                        responseBuilder.append(currentGenerationText)
                    } else if (responseBuilder.isEmpty() && toolResult.content.isNotBlank()) {
                        responseBuilder.append(toolResult.content)
                    }
                }

                val finalText = responseBuilder.toString()

                // Finalize assistant message and update session history once
                val resolvedText = when {
                    finalText.isNotBlank() -> finalText
                    rawFinalText.isNotBlank() -> rawFinalText
                    finalThought.isNotBlank() -> finalThought
                    searchResults.isNotEmpty() -> {
                        // Fallback synthesis directly from search results if model silently stopped or choked on prompt
                        buildString {
                            appendLine("Based on web search results, here is what I found:")
                            appendLine()
                            searchResults.take(3).forEach { res ->
                                val cleanTitle = res.title.substringBefore("-").substringBefore("|").trim()
                                appendLine("• **$cleanTitle**: ${res.snippet.trim()}")
                            }
                            appendLine()
                            appendLine("Please let me know if you would like more details!")
                        }.trim()
                    }
                    else -> "I couldn't generate a response. Please try again with a shorter prompt."
                }

                updateSessionMessages(targetSessionId) { msgs ->
                    msgs.map { msg ->
                        if (msg.id == assistantMessageId) {
                            msg.copy(
                                text = resolvedText,
                                thoughtText = if (resolvedText == finalThought) "" else finalThought,
                                searchResults = searchResults,
                                searchImages = if (currentSearchImages.isNotEmpty()) currentSearchImages else msg.searchImages,
                                isStreaming = false,
                                isThinking = false,
                                isSearchingWeb = false,
                                isExecutingTool = false,
                                toolExecutionStatus = null
                            )
                        } else msg
                    }
                }

                // Persist completed session to storage
                val completedSession = _sessions.value.find { it.id == targetSessionId }
                if (completedSession != null) {
                    chatStorage.saveSession(completedSession)
                }

            } finally {
                if (activeGeneratingSessionId.value == targetSessionId) {
                    activeGeneratingSessionId.value = null
                    if (_currentSessionId.value == targetSessionId) {
                        _isGenerating.value = false
                    }
                }
                try {
                    if (wakeLock?.isHeld == true) {
                        wakeLock.release()
                    }
                } catch (_: Exception) {}
            }
        }
    }

    fun createNewChat() {
        persistChat()

        val newSessionId = UUID.randomUUID().toString()
        _currentSessionId.value = newSessionId
        _messages.value = emptyList()
        _inputText.value = ""
        _isGenerating.value = false
        // Notice: Do NOT cancel activeGenerationJob! Previous chat keeps generating in background
    }

    fun refreshSessions(targetSessionId: String? = null) {
        viewModelScope.launch {
            val loaded = chatStorage.loadSessions()
            _sessions.value = loaded
            if (targetSessionId != null) {
                val target = loaded.find { it.id == targetSessionId }
                if (target != null) {
                    _currentSessionId.value = target.id
                    _messages.value = target.messages
                    _isGenerating.value = (activeGeneratingSessionId.value == target.id)
                    return@launch
                }
            }
            if (_sessions.value.none { it.id == _currentSessionId.value } && loaded.isNotEmpty()) {
                val latest = loaded.first()
                _currentSessionId.value = latest.id
                _messages.value = latest.messages
            }
        }
    }

    fun selectSession(sessionId: String) {
        persistChat()
        val inMemory = _sessions.value.find { it.id == sessionId }
        if (inMemory != null) {
            _currentSessionId.value = inMemory.id
            _messages.value = inMemory.messages
            _inputText.value = ""
            _isGenerating.value = (activeGeneratingSessionId.value == inMemory.id)
        } else {
            refreshSessions(targetSessionId = sessionId)
        }
    }

    fun deleteSession(sessionId: String) {
        if (activeGeneratingSessionId.value == sessionId) {
            stopGeneration()
        }
        viewModelScope.launch {
            val updated = chatStorage.deleteSession(sessionId)
            _sessions.value = updated
            if (_currentSessionId.value == sessionId) {
                if (updated.isNotEmpty()) {
                    val next = updated.first()
                    _currentSessionId.value = next.id
                    _messages.value = next.messages
                    _isGenerating.value = (activeGeneratingSessionId.value == next.id)
                } else {
                    val newId = UUID.randomUUID().toString()
                    _currentSessionId.value = newId
                    _messages.value = emptyList()
                    _isGenerating.value = false
                }
            }
        }
    }

    fun deleteCurrentChat() {
        deleteSession(_currentSessionId.value)
    }

    fun clearAllChats() {
        activeGenerationJob?.cancel()
        _isGenerating.value = false
        _messages.value = emptyList()
        _sessions.value = emptyList()
        val newId = UUID.randomUUID().toString()
        _currentSessionId.value = newId
        viewModelScope.launch {
            chatStorage.clearAllSessions()
            engine?.clearConversation()
        }
    }

    fun clearChat() {
        deleteCurrentChat()
    }

    fun renameCurrentChat(newTitle: String) {
        if (newTitle.isBlank()) return
        viewModelScope.launch {
            val updated = chatStorage.renameSession(_currentSessionId.value, newTitle)
            _sessions.value = updated
        }
    }

    fun regenerateLastResponse() {
        val msgs = _messages.value
        val lastUserIndex = msgs.indexOfLast { it.role == MessageRole.USER }
        if (lastUserIndex == -1) return
        val userMsg = msgs[lastUserIndex]

        activeGenerationJob?.cancel()
        _isGenerating.value = false

        // Keep all messages up to the last user message
        val prunedMessages = msgs.subList(0, lastUserIndex + 1)
        val eng = engine ?: return

        val newAssistantId = UUID.randomUUID().toString()
        val newAssistantMessage = ChatMessage(
            id = newAssistantId,
            role = MessageRole.ASSISTANT,
            text = "",
            isStreaming = true,
            isThinking = _config.value.enableThinking,
            isSearchingWeb = _isWebSearchEnabled.value,
            isImageAnalysis = userMsg.isImageAnalysis
        )

        val currSessionId = _currentSessionId.value
        updateSessionMessages(currSessionId) { prunedMessages + newAssistantMessage }
        _isGenerating.value = true

        val imageBytesToSend = if (userMsg.isImageAnalysis && userMsg.imagePath != null) {
            try { java.io.File(userMsg.imagePath).readBytes() } catch (_: Exception) { null }
        } else null

        val prompt = if (userMsg.text.isNotBlank()) userMsg.text else "Examine this image in full detail. Transcribe and extract all visible text, numbers, headings, tables, labels, or data exactly as shown. If tabular data is present, format it into clean Markdown tables with column headers. Answer clearly, accurately, and thoroughly."

        val useSearch = (_isWebSearchEnabled.value || shouldAutoSearch(prompt)) && imageBytesToSend == null

        startGeneration(
            targetSessionId = currSessionId,
            prompt = prompt,
            assistantMessageId = newAssistantId,
            eng = eng,
            useWebSearch = useSearch,
            allowFallback = !useSearch,
            imageBytes = imageBytesToSend
        )
    }

    fun editAndResendMessage(messageId: String, newText: String) {
        val msgs = _messages.value
        val targetIndex = msgs.indexOfFirst { it.id == messageId }
        if (targetIndex == -1) return
        val originalMsg = msgs[targetIndex]

        activeGenerationJob?.cancel()
        _isGenerating.value = false

        // Keep messages strictly before the target message
        val prefixMessages = msgs.subList(0, targetIndex)
        val updatedUserMsg = originalMsg.copy(text = newText)

        val eng = engine ?: return
        val newAssistantId = UUID.randomUUID().toString()
        val imageBytesToSend = if (updatedUserMsg.isImageAnalysis && updatedUserMsg.imagePath != null) {
            try { java.io.File(updatedUserMsg.imagePath).readBytes() } catch (_: Exception) { null }
        } else null
        val useSearch = (_isWebSearchEnabled.value || shouldAutoSearch(newText)) && imageBytesToSend == null

        val newAssistantMessage = ChatMessage(
            id = newAssistantId,
            role = MessageRole.ASSISTANT,
            text = "",
            isStreaming = true,
            isThinking = _config.value.enableThinking,
            isSearchingWeb = useSearch,
            isImageAnalysis = updatedUserMsg.isImageAnalysis
        )

        val currSessionId = _currentSessionId.value
        updateSessionMessages(currSessionId) { prefixMessages + updatedUserMsg + newAssistantMessage }
        _isGenerating.value = true

        startGeneration(
            targetSessionId = currSessionId,
            prompt = newText,
            assistantMessageId = newAssistantId,
            eng = eng,
            useWebSearch = useSearch,
            allowFallback = !useSearch,
            imageBytes = imageBytesToSend
        )
    }

    fun dismissError() {
        _errorMessage.value = null
    }

    override fun onCleared() {
        super.onCleared()
        activeGenerationJob?.cancel()
        ttsManager.release()
    }
}
