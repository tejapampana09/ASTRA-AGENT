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

data class ChatMessage(
    val id: String = UUID.randomUUID().toString(),
    val role: MessageRole,
    val text: String,
    val thoughtText: String = "",
    val searchResults: List<SearchResult> = emptyList(),
    val isStreaming: Boolean = false,
    val isThinking: Boolean = false,
    val isSearchingWeb: Boolean = false,
    val isImageAnalysis: Boolean = false,
    @Transient val imageBitmap: Bitmap? = null,
    val imagePath: String? = null,
    val whatsAppAction: com.teja.gemmmobile.assistant.WhatsAppAction? = null,
    val callAction: com.teja.gemmmobile.assistant.CallAction? = null
)

class ChatViewModel(application: Application) : AndroidViewModel(application) {

    val modelManager = ModelManager(application.applicationContext)
    private val chatStorage = ChatStorage(application.applicationContext)
    private val webSearchClient = WebSearchClient()
    val memoryManager = MemoryManager(application.applicationContext)
    private var engine: GemmaEngine? = null

    val installState: StateFlow<ModelInstallState> = modelManager.installState

    private val _engineState = MutableStateFlow<EngineState>(EngineState.Uninitialized)
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

    private val _errorMessage = MutableStateFlow<String?>(null)
    val errorMessage: StateFlow<String?> = _errorMessage.asStateFlow()

    private val applicationScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var activeGenerationJob: Job? = null
    val activeGeneratingSessionId = MutableStateFlow<String?>(null)

    private val _showAssistantOverlay = MutableStateFlow(false)
    val showAssistantOverlay: StateFlow<Boolean> = _showAssistantOverlay.asStateFlow()

    fun openAssistantOverlay() {
        _showAssistantOverlay.value = true
    }

    fun closeAssistantOverlay() {
        _showAssistantOverlay.value = false
    }

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
        // Auto-start engine when model becomes available
        viewModelScope.launch {
            installState.collect { state ->
                if (state is ModelInstallState.Installed && _engineState.value is EngineState.Uninitialized) {
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
        val sessionList = _sessions.value.toMutableList()
        val index = sessionList.indexOfFirst { it.id == sessionId }
        val oldSession = if (index != -1) sessionList[index] else {
            ChatSession(id = sessionId, title = "New Chat", messages = emptyList())
        }
        val updatedMessages = transform(oldSession.messages)

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
        _sessions.value = sessionList.sortedByDescending { it.updatedAt }

        if (_currentSessionId.value == sessionId) {
            _messages.value = updatedMessages
        }
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
            engine?.updateConfig(newConfig)
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
            engine?.close()
            engine = null
            _engineState.value = EngineState.Uninitialized
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
            _engineState.value = EngineState.Loading("Initializing model...")
            engine?.close()

            val newEngine = GemmaEngine(modelFile.absolutePath, _config.value)
            engine = newEngine

            // Mirror engine state
            val stateCollectionJob = launch {
                newEngine.engineState.collect { state ->
                    _engineState.value = state
                    if (state is EngineState.Error) {
                        _errorMessage.value = state.message
                    }
                }
            }

            val result = newEngine.initialize()
            if (result.isFailure) {
                val err = result.exceptionOrNull()?.localizedMessage ?: "Model loading failure"
                _errorMessage.value = err
                _engineState.value = EngineState.Error(err)
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
        var query = raw.trim()
        val prefixes = listOf(
            "now search for ",
            "now search ",
            "please search for ",
            "please search ",
            "search for ",
            "search ",
            "google ",
            "find "
        )
        for (p in prefixes) {
            if (query.startsWith(p, ignoreCase = true)) {
                val candidate = query.substring(p.length).trim()
                if (candidate.isNotBlank()) {
                    query = candidate
                    break
                }
            }
        }
        return query
    }

    private fun shouldAutoSearch(prompt: String): Boolean {
        val p = prompt.lowercase().trim()
        val searchKeywords = listOf(
            "search", "find", "who is", "what is", "where is", "when is", "which is",
            "latest", "recent", "today", "yesterday", "current", "news",
            "portal", "website", "link", "url", "login", "cutoff", "admissions",
            "admission", "results", "result", "score", "match", "weather",
            "price", "cost", "stock", "release date", "movie", "srm", "exam", "syllabus",
            "hall ticket", "live", "update", "updates", "schedule", "ipl", "cricket",
            "minister", "president", "ceo", "governor", "university", "college",
            "online", "official", "fees", "fee"
        )
        return searchKeywords.any { keyword ->
            if (keyword.contains(" ")) p.contains(keyword)
            else Regex("\\b${Regex.escape(keyword)}\\b", RegexOption.IGNORE_CASE).containsMatchIn(p)
        }
    }

    private fun indicatesLackOfKnowledge(text: String): Boolean {
        val lower = text.lowercase()
        val phrases = listOf(
            "i don't have access to real-time",
            "i do not have access to real-time",
            "i don't have access to current",
            "i do not have access to current",
            "i cannot access real-time",
            "i cannot browse the internet",
            "i can't browse the internet",
            "i don't have the ability to browse",
            "my knowledge cutoff",
            "as an ai, i cannot provide real-time",
            "i don't have real-time information",
            "i do not have real-time information"
        )
        return phrases.any { lower.contains(it) }
    }

    fun onInputTextChanged(text: String) {
        _inputText.value = text
    }

    fun attachDocument(document: ExtractedDocument) {
        _attachedDocument.value = document
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

        ttsManager.stop()

        // Check for WhatsApp action intent (e.g. "send hi to Manoj in whatsapp")
        val whatsAppParsed = if (doc == null) com.teja.gemmmobile.assistant.WhatsAppActionHandler.parseWhatsAppIntent(rawInput) else null
        if (whatsAppParsed != null) {
            handleWhatsAppIntent(rawInput, whatsAppParsed.first, whatsAppParsed.second)
            return
        }

        // Check for phone call intent (e.g. "call manoj", "manoj ki call cheyi")
        val callTarget = if (doc == null) com.teja.gemmmobile.assistant.CallActionHandler.parseCallIntent(rawInput) else null
        if (callTarget != null) {
            handleCallIntent(rawInput, callTarget)
            return
        }


        // Check if there is a pending WhatsApp confirmation in the current chat
        val lastMsg = _messages.value.lastOrNull()
        if (lastMsg != null && lastMsg.whatsAppAction?.status == com.teja.gemmmobile.assistant.WhatsAppStatus.AWAITING_CONFIRMATION) {
            val pendingAction = lastMsg.whatsAppAction
            val cleanLower = rawInput.lowercase().trim('.', '!', '?', ' ')
            val isConfirm = cleanLower in listOf(
                "yes", "send", "pampu", "confirm", "send it", "avunu", "ha", "sure", "ok", "okay", "cheyi", "send cheyi", "proceed", "yes please", "do it", "y"
            ) || cleanLower.startsWith("yes") || cleanLower.startsWith("send")
            val isCancel = cleanLower in listOf(
                "no", "cancel", "vaddu", "don't send", "dont send", "stop", "abort", "oddu", "n"
            ) || cleanLower.startsWith("no") || cleanLower.startsWith("cancel")

            if (isConfirm) {
                _inputText.value = ""
                confirmAndSendWhatsAppAction(pendingAction)
                return
            } else if (isCancel) {
                _inputText.value = ""
                cancelWhatsAppAction(pendingAction)
                return
            }
        }

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

        // Web search is STRICTLY manual (only if user explicitly clicked the Web toggle, and never on images)
        val useWebSearch = _isWebSearchEnabled.value && !isImage

        _attachedDocument.value = null
        val userMessageId = UUID.randomUUID().toString()
        val savedImagePath = if (isImage && doc?.imageBytes != null) {
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
            imageBitmap = if (isImage) doc?.previewBitmap else null,
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
            isThinking = _config.value.enableThinking,
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

    fun handleWhatsAppIntent(contactQuery: String, messageText: String) {
        handleWhatsAppIntent("Send \"$messageText\" to $contactQuery on WhatsApp", contactQuery, messageText)
    }

    fun handleWhatsAppIntent(userPrompt: String, contactQuery: String, messageText: String) {
        val currSessionId = _currentSessionId.value
        _inputText.value = ""

        val userMessage = ChatMessage(
            id = UUID.randomUUID().toString(),
            role = MessageRole.USER,
            text = userPrompt
        )

        val context = getApplication<Application>()
        val matches = com.teja.gemmmobile.assistant.ContactHelper.searchContact(context, contactQuery)

        val assistantMessage: ChatMessage
        if (matches.isNotEmpty()) {
            val contact = matches.first()
            val composedMsg = com.teja.gemmmobile.assistant.WhatsAppActionHandler.resolveMessageBody(contact.name, messageText)

            val action = com.teja.gemmmobile.assistant.WhatsAppAction(
                recipientName = contact.name,
                messageText = composedMsg,
                rawIntent = messageText,
                matchedNumber = contact.phoneNumber,
                candidateContacts = matches,
                status = com.teja.gemmmobile.assistant.WhatsAppStatus.AWAITING_CONFIRMATION
            )

            val responseText = "I found **${contact.name}** (${contact.formattedNumber}). I've drafted this message:\n\n> *\"$composedMsg\"*\n\nWould you like me to send it on WhatsApp?"

            assistantMessage = ChatMessage(
                id = UUID.randomUUID().toString(),
                role = MessageRole.ASSISTANT,
                text = responseText,
                whatsAppAction = action
            )
        } else {
            val composedMsg = com.teja.gemmmobile.assistant.WhatsAppActionHandler.resolveMessageBody(contactQuery, messageText)
            val responseText = "I couldn't find \"$contactQuery\" in your contacts. Please ensure Contacts permission is granted or check the saved contact name."
            assistantMessage = ChatMessage(
                id = UUID.randomUUID().toString(),
                role = MessageRole.ASSISTANT,
                text = responseText,
                whatsAppAction = com.teja.gemmmobile.assistant.WhatsAppAction(
                    recipientName = contactQuery,
                    messageText = composedMsg,
                    rawIntent = messageText,
                    matchedNumber = null,
                    candidateContacts = emptyList(),
                    status = com.teja.gemmmobile.assistant.WhatsAppStatus.NO_CONTACT_FOUND
                )
            )
        }

        updateSessionMessages(currSessionId) { msgs ->
            msgs + userMessage + assistantMessage
        }
        val updatedSession = _sessions.value.find { it.id == currSessionId }
        if (updatedSession != null) {
            applicationScope.launch { chatStorage.saveSession(updatedSession) }
        }
    }

    fun confirmAndSendWhatsAppAction(action: com.teja.gemmmobile.assistant.WhatsAppAction?) {
        if (action == null) return
        val number = action.matchedNumber ?: return
        val context = getApplication<Application>()

        // 1. Permanently remember this contact so subsequent lookups are instant
        com.teja.gemmmobile.assistant.ContactMemoryManager.rememberContact(
            context = context,
            queryKey = action.recipientName,
            fullName = action.recipientName,
            phoneNumber = number,
            formattedNumber = number
        )

        // 2. Send via WhatsApp & Accessibility Service
        val a11yEnabled = com.teja.gemmmobile.assistant.GemmaAccessibilityService.isAccessibilityEnabled(context)
        com.teja.gemmmobile.assistant.WhatsAppActionHandler.sendWhatsAppDirect(
            context = context,
            phoneNumber = number,
            message = action.messageText,
            autoSend = true
        )

        // 3. Update chat session UI
        val currSessionId = _currentSessionId.value
        val newStatus = if (a11yEnabled) com.teja.gemmmobile.assistant.WhatsAppStatus.SENT_DIRECTLY else com.teja.gemmmobile.assistant.WhatsAppStatus.READY_TO_SEND
        val confirmationText = if (a11yEnabled) {
            "✓ Sent \"${action.messageText}\" to **${action.recipientName}** ($number) on WhatsApp."
        } else {
            "✓ Prepared message for **${action.recipientName}** ($number) in WhatsApp."
        }

        updateSessionMessages(currSessionId) { msgs ->
            msgs.map { msg ->
                if (msg.whatsAppAction != null && msg.whatsAppAction.status == com.teja.gemmmobile.assistant.WhatsAppStatus.AWAITING_CONFIRMATION) {
                    msg.copy(
                        text = confirmationText,
                        whatsAppAction = msg.whatsAppAction.copy(status = newStatus)
                    )
                } else msg
            }
        }
        persistChat()
    }

    fun cancelWhatsAppAction(action: com.teja.gemmmobile.assistant.WhatsAppAction?) {
        val currSessionId = _currentSessionId.value
        updateSessionMessages(currSessionId) { msgs ->
            msgs.map { msg ->
                if (msg.whatsAppAction != null && msg.whatsAppAction.status == com.teja.gemmmobile.assistant.WhatsAppStatus.AWAITING_CONFIRMATION) {
                    msg.copy(
                        text = "Cancelled sending message to **${action?.recipientName ?: "contact"}**.",
                        whatsAppAction = msg.whatsAppAction.copy(status = com.teja.gemmmobile.assistant.WhatsAppStatus.CANCELLED)
                    )
                } else msg
            }
        }
        persistChat()
    }

    fun selectWhatsAppCandidate(candidate: com.teja.gemmmobile.assistant.ContactMatch, action: com.teja.gemmmobile.assistant.WhatsAppAction) {
        val currSessionId = _currentSessionId.value
        val raw = if (action.rawIntent.isNotBlank()) action.rawIntent else action.messageText
        val reComposed = com.teja.gemmmobile.assistant.WhatsAppActionHandler.resolveMessageBody(candidate.name, raw)

        updateSessionMessages(currSessionId) { msgs ->
            msgs.map { msg ->
                if (msg.whatsAppAction != null && msg.whatsAppAction.status == com.teja.gemmmobile.assistant.WhatsAppStatus.AWAITING_CONFIRMATION) {
                    msg.copy(
                        text = "Selected **${candidate.name}** (${candidate.formattedNumber}). I've drafted this message:\n\n> *\"$reComposed\"*\n\nWould you like me to send it on WhatsApp?",
                        whatsAppAction = msg.whatsAppAction.copy(
                            recipientName = candidate.name,
                            matchedNumber = candidate.phoneNumber,
                            messageText = reComposed
                        )
                    )
                } else msg
            }
        }
    }

    fun executeWhatsAppAction(action: com.teja.gemmmobile.assistant.WhatsAppAction) {
        confirmAndSendWhatsAppAction(action)
    }

    // ─── Phone Call handling ───────────────────────────────────────────────────

    fun handleCallIntent(userPrompt: String, contactQuery: String) {
        val currSessionId = _currentSessionId.value
        _inputText.value = ""

        val userMessage = ChatMessage(
            id = UUID.randomUUID().toString(),
            role = MessageRole.USER,
            text = userPrompt
        )

        val context = getApplication<Application>()
        val matches = com.teja.gemmmobile.assistant.ContactHelper.searchContact(context, contactQuery)

        val assistantMessage: ChatMessage
        if (matches.isNotEmpty()) {
            val contact = matches.first()
            val action = com.teja.gemmmobile.assistant.CallAction(
                recipientName = contact.name,
                matchedNumber = contact.phoneNumber,
                candidateContacts = matches,
                status = com.teja.gemmmobile.assistant.CallStatus.CALLING
            )
            val responseText = "Calling **${contact.name}** (${contact.formattedNumber})…"
            // Place the call immediately — no confirmation needed for calls
            com.teja.gemmmobile.assistant.CallActionHandler.makeCall(context, contact.phoneNumber)
            com.teja.gemmmobile.assistant.ContactMemoryManager.rememberContact(
                context = context,
                queryKey = contactQuery,
                fullName = contact.name,
                phoneNumber = contact.phoneNumber,
                formattedNumber = contact.formattedNumber
            )
            assistantMessage = ChatMessage(
                id = UUID.randomUUID().toString(),
                role = MessageRole.ASSISTANT,
                text = responseText,
                callAction = action.copy(status = com.teja.gemmmobile.assistant.CallStatus.DIALED)
            )
        } else {
            val action = com.teja.gemmmobile.assistant.CallAction(
                recipientName = contactQuery,
                matchedNumber = null,
                candidateContacts = emptyList(),
                status = com.teja.gemmmobile.assistant.CallStatus.NO_CONTACT_FOUND
            )
            val responseText = "I couldn't find \"$contactQuery\" in your contacts."
            assistantMessage = ChatMessage(
                id = UUID.randomUUID().toString(),
                role = MessageRole.ASSISTANT,
                text = responseText,
                callAction = action
            )
        }

        updateSessionMessages(currSessionId) { msgs -> msgs + userMessage + assistantMessage }
        persistChat()
    }


    fun openAccessibilitySettings() {
        try {
            val intent = com.teja.gemmmobile.assistant.GemmaAccessibilityService.getAccessibilitySettingsIntent()
            getApplication<Application>().startActivity(intent)
        } catch (_: Exception) {}
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
                        val fetchedResults = kotlinx.coroutines.withTimeoutOrNull(3500L) {
                            webSearchClient.search(cleanQuery, maxResults = 3)
                        }
                        if (fetchedResults != null && fetchedResults.isNotEmpty()) {
                            searchResults = fetchedResults
                            val contextSnippets = searchResults.mapIndexed { idx, res ->
                                "[${idx + 1}] Title: ${res.title}\nSnippet: ${res.snippet}\nSource URL: ${res.url}"
                            }.joinToString("\n\n")

                            searchContext = "Live Real-Time Web Search Results:\n$contextSnippets"
                        }
                    } catch (t: Throwable) {
                        Log.w(TAG, "[$TAG] Web search failed", t)
                    } finally {
                        updateSessionMessages(targetSessionId) { msgs ->
                            msgs.map { msg ->
                                if (msg.id == assistantMessageId) msg.copy(searchResults = searchResults, isSearchingWeb = false) else msg
                            }
                        }
                    }
                }

                // Retrieve persistent memories and history from target session
                val memoryContext = memoryManager.getFormattedMemoryPrompt()
                val sessionSnapshot = _sessions.value.find { it.id == targetSessionId }
                val targetMsgs = sessionSnapshot?.messages ?: _messages.value
                val previousTurns = targetMsgs
                    .filter { it.text.isNotBlank() && it.id != assistantMessageId }
                    .takeLast(4)

                val historyContext = if (previousTurns.isNotEmpty()) {
                    "Recent Conversation History:\n" + previousTurns.joinToString("\n") {
                        (if (it.role == MessageRole.USER) "User" else "Assistant") + ": " + it.text
                    }
                } else ""

                val effectivePrompt = buildString {
                    if (imageBytes == null) {
                        if (memoryContext.isNotBlank()) {
                            appendLine(memoryContext)
                            appendLine()
                        }
                        if (historyContext.isNotBlank()) {
                            appendLine(historyContext)
                            appendLine()
                        }
                    }
                    if (searchContext.isNotBlank()) {
                        appendLine(searchContext)
                        appendLine()
                    }
                    appendLine(prompt)
                    if (searchContext.isNotBlank()) {
                        appendLine("Important Instructions: You have access to real-time live internet information via the Web Search Results above. Directly answer the user's question with full detail using the search results. Mention relevant facts, names, or URLs. Format all URLs as clickable links. Do NOT say you cannot access the internet, as the live web search results are provided right above.")
                    }
                }.trim()

                val responseBuilder = StringBuilder()
                val thoughtBuilder = StringBuilder()
                var inThoughtTag = false

                eng.sendMessage(effectivePrompt, imageBytes)
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
                            if (chunkText.contains("<thought>") || inThoughtTag) {
                                var remaining = chunkText
                                while (remaining.isNotEmpty()) {
                                    if (!inThoughtTag) {
                                        val startIdx = remaining.indexOf("<thought>")
                                        if (startIdx != -1) {
                                            responseBuilder.append(remaining.substring(0, startIdx))
                                            remaining = remaining.substring(startIdx + "<thought>".length)
                                            inThoughtTag = true
                                        } else {
                                            responseBuilder.append(remaining)
                                            remaining = ""
                                        }
                                    } else {
                                        val endIdx = remaining.indexOf("</thought>")
                                        if (endIdx != -1) {
                                            thoughtBuilder.append(remaining.substring(0, endIdx))
                                            remaining = remaining.substring(endIdx + "</thought>".length)
                                            inThoughtTag = false
                                        } else {
                                            thoughtBuilder.append(remaining)
                                            remaining = ""
                                        }
                                    }
                                }
                            } else {
                                responseBuilder.append(chunkText)
                            }
                        }

                        val currentText = responseBuilder.toString()
                        val currentThought = thoughtBuilder.toString()
                        val stillThinking = currentText.isEmpty() && currentThought.isNotEmpty()

                        updateSessionMessages(targetSessionId) { msgs ->
                            msgs.map { msg ->
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

                val finalText = responseBuilder.toString()

                if (allowFallback && indicatesLackOfKnowledge(finalText)) {
                    Log.d(TAG, "[$TAG] Model indicated lack of real-time knowledge. Auto-triggering web search fallback...")
                    updateSessionMessages(targetSessionId) { msgs ->
                        msgs.map { msg ->
                            if (msg.id == assistantMessageId) {
                                msg.copy(text = "", thoughtText = "", isSearchingWeb = true, isStreaming = true)
                            } else msg
                        }
                    }
                    startGeneration(
                        targetSessionId = targetSessionId,
                        prompt = prompt,
                        assistantMessageId = assistantMessageId,
                        eng = eng,
                        useWebSearch = true,
                        allowFallback = false
                    )
                    return@launch
                }

                // Finalize assistant message
                updateSessionMessages(targetSessionId) { msgs ->
                    msgs.map { msg ->
                        if (msg.id == assistantMessageId) {
                            msg.copy(isStreaming = false, isThinking = false, isSearchingWeb = false)
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

    fun selectSession(sessionId: String) {
        if (sessionId == _currentSessionId.value) return
        persistChat()

        val target = _sessions.value.find { it.id == sessionId }
        if (target != null) {
            _currentSessionId.value = target.id
            _messages.value = target.messages
            _inputText.value = ""
            // Reflect generation state if the newly selected session is generating
            _isGenerating.value = (activeGeneratingSessionId.value == target.id)
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

        startGeneration(
            targetSessionId = currSessionId,
            prompt = prompt,
            assistantMessageId = newAssistantId,
            eng = eng,
            useWebSearch = _isWebSearchEnabled.value,
            allowFallback = !_isWebSearchEnabled.value,
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
        val newAssistantMessage = ChatMessage(
            id = newAssistantId,
            role = MessageRole.ASSISTANT,
            text = "",
            isStreaming = true,
            isThinking = _config.value.enableThinking,
            isSearchingWeb = _isWebSearchEnabled.value,
            isImageAnalysis = updatedUserMsg.isImageAnalysis
        )

        val currSessionId = _currentSessionId.value
        updateSessionMessages(currSessionId) { prefixMessages + updatedUserMsg + newAssistantMessage }
        _isGenerating.value = true

        val imageBytesToSend = if (updatedUserMsg.isImageAnalysis && updatedUserMsg.imagePath != null) {
            try { java.io.File(updatedUserMsg.imagePath).readBytes() } catch (_: Exception) { null }
        } else null

        startGeneration(
            targetSessionId = currSessionId,
            prompt = newText,
            assistantMessageId = newAssistantId,
            eng = eng,
            useWebSearch = _isWebSearchEnabled.value,
            allowFallback = !_isWebSearchEnabled.value,
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
        engine?.close()
        engine = null
    }
}
