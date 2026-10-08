package com.teja.gemmmobile.assistant

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.imePadding
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.core.view.WindowCompat
import androidx.lifecycle.lifecycleScope
import com.teja.gemmmobile.MainActivity
import com.teja.gemmmobile.ai.GemmaRepository
import com.teja.gemmmobile.audio.TtsManager
import com.teja.gemmmobile.memory.MemoryManager
import com.teja.gemmmobile.search.WebSearchClient
import com.teja.gemmmobile.storage.ChatSession
import com.teja.gemmmobile.storage.ChatStorage
import com.teja.gemmmobile.ui.ChatMessage
import com.teja.gemmmobile.ui.MessageRole
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.ui.graphics.Color
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.launch
import java.util.UUID

class AssistantActivity : ComponentActivity() {

    companion object {
        const val EXTRA_SESSION_ID = "EXTRA_SESSION_ID"
        const val EXTRA_INITIAL_QUERY = "EXTRA_INITIAL_QUERY"
    }

    private lateinit var ttsManager: TtsManager
    private lateinit var chatStorage: ChatStorage
    private lateinit var memoryManager: MemoryManager
    private val webSearchClient = WebSearchClient()

    private var activeJob: Job? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, false)

        ttsManager = TtsManager(this)
        chatStorage = ChatStorage(this)
        memoryManager = MemoryManager(this)

        val initialSessionId = intent?.getStringExtra(EXTRA_SESSION_ID) ?: UUID.randomUUID().toString()

        val assistantDarkScheme = darkColorScheme(
            primary = Color(0xFF8AB4F8),
            onPrimary = Color(0xFF041E49),
            surface = Color(0xFF1E1F22),
            onSurface = Color(0xFFE8EAED),
            surfaceVariant = Color(0xFF28292D),
            onSurfaceVariant = Color(0xFFC4C7C5),
            background = Color(0xFF1E1F22),
            onBackground = Color(0xFFE8EAED)
        )

        setContent {
            MaterialTheme(colorScheme = assistantDarkScheme) {
                var currentSessionId by remember { mutableStateOf(initialSessionId) }
            var userQuery by remember { mutableStateOf("") }
            var assistantResponse by remember { mutableStateOf("") }
            var thoughtText by remember { mutableStateOf("") }
            var isThinking by remember { mutableStateOf(false) }
            var isStreaming by remember { mutableStateOf(false) }

            val isSpeaking by ttsManager.isSpeaking.collectAsState()

            var pendingAction by remember { mutableStateOf<WhatsAppAction?>(null) }
            var pendingCallAction by remember { mutableStateOf<CallAction?>(null) }

            val callPermissionLauncher = rememberLauncherForActivityResult(
                contract = ActivityResultContracts.RequestPermission()
            ) { granted ->
                val action = pendingCallAction
                if (granted && action?.matchedNumber != null) {
                    pendingCallAction = action.copy(status = CallStatus.CALLING)
                    assistantResponse = "Calling **${action.recipientName}** (${action.matchedNumber})…"
                    ttsManager.speak(UUID.randomUUID().toString(), "Calling ${action.recipientName} now")
                    lifecycleScope.launch {
                        delay(350)
                        CallActionHandler.makeCall(this@AssistantActivity, action.matchedNumber)
                        delay(600)
                        finish()
                    }
                } else {
                    Toast.makeText(this@AssistantActivity, "Call permission needed to place calls directly", Toast.LENGTH_SHORT).show()
                    action?.matchedNumber?.let { number ->
                        CallActionHandler.makeCall(this@AssistantActivity, number)
                    }
                }
            }

            val smsPermissionLauncher = rememberLauncherForActivityResult(
                contract = ActivityResultContracts.RequestPermission()
            ) { granted ->
                val action = pendingAction
                if (granted && action?.matchedNumber != null) {
                    val sent = SmsActionHandler.sendSmsDirect(
                        context = this@AssistantActivity,
                        phoneNumber = action.matchedNumber,
                        message = action.messageText
                    )
                    if (sent) {
                        ContactMemoryManager.rememberContact(
                            context = this@AssistantActivity,
                            queryKey = action.recipientName,
                            fullName = action.recipientName,
                            phoneNumber = action.matchedNumber,
                            formattedNumber = action.matchedNumber
                        )
                        pendingAction = action.copy(status = WhatsAppStatus.SENT_DIRECTLY)
                        assistantResponse = "✓ Sent message to **${action.recipientName}** in background."
                        ttsManager.speak(UUID.randomUUID().toString(), "Sent message to ${action.recipientName} in background")
                        lifecycleScope.launch {
                            delay(1200)
                            finish()
                        }
                    }
                } else {
                    Toast.makeText(this@AssistantActivity, "SMS permission needed to send silent messages", Toast.LENGTH_SHORT).show()
                }
            }

            fun performDirectCall(number: String, recipientName: String) {
                val hasPermission = ContextCompat.checkSelfPermission(
                    this@AssistantActivity,
                    Manifest.permission.CALL_PHONE
                ) == PackageManager.PERMISSION_GRANTED

                if (hasPermission) {
                    pendingCallAction = pendingCallAction?.copy(status = CallStatus.CALLING)
                    assistantResponse = "Calling **$recipientName** ($number)…"
                    ttsManager.speak(UUID.randomUUID().toString(), "Calling $recipientName now")

                    lifecycleScope.launch {
                        delay(350)
                        CallActionHandler.makeCall(this@AssistantActivity, number)
                        delay(600)
                        finish()
                    }
                } else {
                    callPermissionLauncher.launch(Manifest.permission.CALL_PHONE)
                }
            }

            fun performDirectSmsSend(action: WhatsAppAction) {
                val number = action.matchedNumber ?: return
                val hasPermission = ContextCompat.checkSelfPermission(
                    this@AssistantActivity,
                    Manifest.permission.SEND_SMS
                ) == PackageManager.PERMISSION_GRANTED

                if (hasPermission) {
                    val sent = SmsActionHandler.sendSmsDirect(
                        context = this@AssistantActivity,
                        phoneNumber = number,
                        message = action.messageText
                    )
                    if (sent) {
                        ContactMemoryManager.rememberContact(
                            context = this@AssistantActivity,
                            queryKey = action.recipientName,
                            fullName = action.recipientName,
                            phoneNumber = number,
                            formattedNumber = number
                        )
                        pendingAction = action.copy(status = WhatsAppStatus.SENT_DIRECTLY)
                        assistantResponse = "✓ Sent message to **${action.recipientName}** in background."
                        ttsManager.speak(UUID.randomUUID().toString(), "Sent message to ${action.recipientName} in background")
                        lifecycleScope.launch {
                            delay(1200)
                            finish()
                        }
                    } else {
                        Toast.makeText(this@AssistantActivity, "Failed to send SMS in background", Toast.LENGTH_SHORT).show()
                    }
                } else {
                    smsPermissionLauncher.launch(Manifest.permission.SEND_SMS)
                }
            }

            fun performWhatsAppSend(action: WhatsAppAction) {
                val number = action.matchedNumber ?: return
                ContactMemoryManager.rememberContact(
                    context = this@AssistantActivity,
                    queryKey = action.recipientName,
                    fullName = action.recipientName,
                    phoneNumber = number,
                    formattedNumber = number
                )

                WhatsAppActionHandler.sendWhatsAppDirect(
                    context = this@AssistantActivity,
                    phoneNumber = number,
                    message = action.messageText,
                    autoSend = true,
                    recipientName = action.recipientName
                )

                pendingAction = action.copy(status = WhatsAppStatus.SENT_DIRECTLY)
                assistantResponse = "✓ Sent WhatsApp message to **${action.recipientName}**."
                ttsManager.speak(UUID.randomUUID().toString(), "Sent WhatsApp message to ${action.recipientName}")

                lifecycleScope.launch {
                    delay(900)
                    finish()
                }
            }

            // Function to generate response with on-device Gemma
            fun generateAnswer(prompt: String) {
                activeJob?.cancel()
                ttsManager.stop()

                userQuery = prompt
                assistantResponse = ""
                thoughtText = ""
                isThinking = true
                isStreaming = true

                activeJob = lifecycleScope.launch {
                    val engine = GemmaRepository.getEngine()
                        ?: GemmaRepository.getOrInitializeEngine(this@AssistantActivity)

                    if (engine == null) {
                        isThinking = false
                        isStreaming = false
                        assistantResponse = "Gemma model is not installed or initializing. Please open the Gemma app to verify model installation."
                        return@launch
                    }

                    // Format prompt with persistent memory and instructions
                    val memoryContext = memoryManager.getFormattedMemoryPrompt()
                    val effectivePrompt = buildString {
                        if (memoryContext.isNotBlank()) {
                            appendLine(memoryContext)
                            appendLine()
                        }
                        appendLine("You are Gemma, an intelligent, helpful voice and mobile assistant.")
                        appendLine(prompt)
                    }.trim()

                    val responseBuilder = StringBuilder()
                    val thoughtBuilder = StringBuilder()
                    var inThoughtTag = false

                    engine.sendMessage(effectivePrompt)
                        .catch { e ->
                            isThinking = false
                            isStreaming = false
                            assistantResponse = "Error generating response: ${e.localizedMessage ?: "Unknown error"}"
                        }
                        .collect { chunk ->
                            if (chunk.thought.isNotEmpty()) {
                                thoughtBuilder.append(chunk.thought)
                                thoughtText = thoughtBuilder.toString()
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
                            assistantResponse = currentText
                            thoughtText = thoughtBuilder.toString()
                            if (currentText.isNotEmpty()) {
                                isThinking = false
                            }
                        }

                    isThinking = false
                    isStreaming = false

                    val finalAnswer = assistantResponse
                    if (finalAnswer.isNotBlank()) {
                        // Automatically speak response out loud with TTS
                        ttsManager.speak(UUID.randomUUID().toString(), finalAnswer)

                        // Synchronize conversation into ChatStorage so it appears in Gemma Mobile history
                        val userMsg = ChatMessage(role = MessageRole.USER, text = prompt)
                        val assistantMsg = ChatMessage(role = MessageRole.ASSISTANT, text = finalAnswer, thoughtText = thoughtText)
                        val sessionTitle = prompt.take(35)
                        val chatSession = ChatSession(
                            id = currentSessionId,
                            title = sessionTitle,
                            createdAt = System.currentTimeMillis(),
                            updatedAt = System.currentTimeMillis(),
                            messages = listOf(userMsg, assistantMsg)
                        )
                        chatStorage.saveSession(chatSession)
                    }
                }
            }

            fun handleCallContact(contactQuery: String) {
                val matches = ContactHelper.searchContact(this@AssistantActivity, contactQuery)
                if (matches.isNotEmpty()) {
                    val best = matches.first()
                    ContactMemoryManager.rememberContact(
                        context = this@AssistantActivity,
                        queryKey = contactQuery,
                        fullName = best.name,
                        phoneNumber = best.phoneNumber,
                        formattedNumber = best.formattedNumber
                    )
                    pendingCallAction = CallAction(
                        recipientName = best.name,
                        matchedNumber = best.phoneNumber,
                        candidateContacts = matches,
                        status = CallStatus.AWAITING_CONFIRMATION
                    )
                    userQuery = "Call $contactQuery"
                    assistantResponse = "Would you like to call **${best.name}** (${best.formattedNumber})?"
                    ttsManager.speak(UUID.randomUUID().toString(), "Would you like to call ${best.name}?")
                } else {
                    val msg = "Couldn't find \"$contactQuery\" in your contacts."
                    userQuery = "Call $contactQuery"
                    assistantResponse = msg
                    ttsManager.speak(UUID.randomUUID().toString(), msg)
                    Toast.makeText(this@AssistantActivity, msg, Toast.LENGTH_LONG).show()
                }
            }

            fun handleMessageSend(recipient: String, message: String, platform: MessagePlatform) {
                val matches = ContactHelper.searchContact(this@AssistantActivity, recipient)
                if (matches.isNotEmpty()) {
                    val best = matches.first()
                    val composed = WhatsAppActionHandler.resolveMessageBody(best.name, message)
                    pendingAction = WhatsAppAction(
                        recipientName = best.name,
                        messageText = composed,
                        rawIntent = message,
                        matchedNumber = best.phoneNumber,
                        candidateContacts = matches,
                        platform = platform,
                        status = WhatsAppStatus.AWAITING_CONFIRMATION
                    )
                    val platformLabel = if (platform == MessagePlatform.BACKGROUND_SMS) "message" else "WhatsApp"
                    userQuery = "Send $platformLabel to $recipient"
                    val platformNotice = if (platform == MessagePlatform.BACKGROUND_SMS) "via Background SMS" else "via WhatsApp"
                    assistantResponse = "Drafted message to **${best.name}** ($platformNotice):\n\n> *\"$composed\"*\n\nSay \"Yes\" or tap Send to send it."
                    ttsManager.speak(UUID.randomUUID().toString(), "I drafted this message to ${best.name}: $composed. Should I send it?")
                } else {
                    val msg = "Couldn't find \"$recipient\" in your contacts."
                    userQuery = "Send message to $recipient"
                    assistantResponse = msg
                    ttsManager.speak(UUID.randomUUID().toString(), msg)
                    Toast.makeText(this@AssistantActivity, msg, Toast.LENGTH_LONG).show()
                }
            }

            fun processQuery(raw: String) {
                val waIntent = WhatsAppActionHandler.parseWhatsAppIntent(raw)
                val smsIntent = SmsActionHandler.parseMessageIntent(raw)
                val callTarget = CallActionHandler.parseCallIntent(raw)
                when {
                    waIntent != null -> handleMessageSend(waIntent.first, waIntent.second, MessagePlatform.WHATSAPP)
                    smsIntent != null -> handleMessageSend(smsIntent.first, smsIntent.second, MessagePlatform.BACKGROUND_SMS)
                    callTarget != null -> handleCallContact(callTarget)
                    else -> generateAnswer(raw)
                }
            }

            val initialQuery = remember { intent?.getStringExtra(EXTRA_INITIAL_QUERY)?.takeIf { it.isNotBlank() } }
            LaunchedEffect(initialQuery) {
                if (!initialQuery.isNullOrBlank()) {
                    processQuery(initialQuery)
                }
            }

            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .imePadding(),
                contentAlignment = Alignment.BottomCenter
            ) {
                GeminiAssistantSheet(
                    onDismiss = {
                        finish()
                    },
                    onOpenInApp = {
                        val openIntent = Intent(this@AssistantActivity, MainActivity::class.java).apply {
                            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP
                            putExtra(MainActivity.EXTRA_SESSION_ID, currentSessionId)
                        }
                        startActivity(openIntent)
                        finish()
                    },
                    onSubmitPrompt = { prompt ->
                        generateAnswer(prompt)
                    },
                    userQuery = userQuery,
                    assistantResponse = assistantResponse,
                    thoughtText = thoughtText,
                    isThinking = isThinking,
                    isStreaming = isStreaming,
                    isSpeaking = isSpeaking,
                    onToggleSpeak = {
                        if (isSpeaking) {
                            ttsManager.stop()
                        } else if (assistantResponse.isNotBlank()) {
                            ttsManager.speak(UUID.randomUUID().toString(), assistantResponse)
                        }
                    },
                    onStopGeneration = {
                        activeJob?.cancel()
                        isStreaming = false
                        isThinking = false
                    },
                    onCallContact = { contactQuery ->
                        handleCallContact(contactQuery)
                    },
                    onWhatsAppSend = { recipient, message ->
                        handleMessageSend(recipient, message, MessagePlatform.WHATSAPP)
                    },
                    onMessageSend = { recipient, message, platform ->
                        handleMessageSend(recipient, message, platform)
                    },
                    pendingWhatsAppAction = pendingAction,
                    onConfirmWhatsAppSend = { action ->
                        if (action.platform == MessagePlatform.BACKGROUND_SMS) {
                            performDirectSmsSend(action)
                        } else {
                            performWhatsAppSend(action)
                        }
                    },
                    onCancelWhatsAppAction = {
                        pendingAction = null
                    },
                    onSelectWhatsAppCandidate = { candidate, action ->
                        val raw = if (action.rawIntent.isNotBlank()) action.rawIntent else action.messageText
                        val reComposed = WhatsAppActionHandler.resolveMessageBody(candidate.name, raw)
                        pendingAction = action.copy(
                            recipientName = candidate.name,
                            matchedNumber = candidate.phoneNumber,
                            messageText = reComposed
                        )
                    },
                    onPlatformChanged = { newPlatform, action ->
                        pendingAction = action.copy(platform = newPlatform)
                    },
                    pendingCallAction = pendingCallAction,
                    onConfirmCall = { action ->
                        action.matchedNumber?.let { number ->
                            performDirectCall(number, action.recipientName)
                        }
                    },
                    onCancelCall = {
                        pendingCallAction = pendingCallAction?.copy(status = CallStatus.CANCELLED)
                        assistantResponse = "Call cancelled."
                        ttsManager.speak(UUID.randomUUID().toString(), "Call cancelled")
                        lifecycleScope.launch {
                            delay(600)
                            pendingCallAction = null
                        }
                    }
                )
            }
        }
    }
}

    override fun onResume() {
        super.onResume()
        GemmaWakeWordService.pauseForAssistant()
    }

    override fun finish() {
        super.finish()
        overridePendingTransition(0, android.R.anim.fade_out)
    }

    override fun onDestroy() {
        super.onDestroy()
        activeJob?.cancel()
        ttsManager.release()
        GemmaWakeWordService.resumeAfterAssistant(this)
    }
}
