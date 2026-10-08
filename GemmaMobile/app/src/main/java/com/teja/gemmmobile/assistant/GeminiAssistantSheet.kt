package com.teja.gemmmobile.assistant

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import com.teja.gemmmobile.ui.MarkdownText
import java.util.Locale

// Gemini signature spectrum colors
val GeminiBlue = Color(0xFF4285F4)
val GeminiPurple = Color(0xFF9B51E0)
val GeminiRed = Color(0xFFEA4335)
val GeminiYellow = Color(0xFFFBBC05)
val GeminiGreen = Color(0xFF34A853)

val GeminiGradient = Brush.linearGradient(
    colors = listOf(
        GeminiBlue,
        GeminiPurple,
        GeminiRed,
        GeminiYellow,
        GeminiGreen
    )
)

val GeminiGlowBrush = Brush.radialGradient(
    colors = listOf(
        GeminiBlue.copy(alpha = 0.50f),
        GeminiPurple.copy(alpha = 0.30f),
        Color.Transparent
    )
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun GeminiAssistantSheet(
    onDismiss: () -> Unit,
    onOpenInApp: () -> Unit,
    onSubmitPrompt: (String) -> Unit,
    userQuery: String = "",
    assistantResponse: String = "",
    thoughtText: String = "",
    isThinking: Boolean = false,
    isStreaming: Boolean = false,
    isSpeaking: Boolean = false,
    onToggleSpeak: () -> Unit = {},
    onStopGeneration: () -> Unit = {},
    onWhatsAppSend: (recipient: String, message: String) -> Unit = { _, _ -> },
    onMessageSend: (recipient: String, message: String, platform: MessagePlatform) -> Unit = { r, m, _ -> onWhatsAppSend(r, m) },
    onCallContact: (String) -> Unit = {},
    pendingWhatsAppAction: WhatsAppAction? = null,
    onConfirmWhatsAppSend: (WhatsAppAction) -> Unit = {},
    onCancelWhatsAppAction: () -> Unit = {},
    onSelectWhatsAppCandidate: (ContactMatch, WhatsAppAction) -> Unit = { _, _ -> },
    onPlatformChanged: (MessagePlatform, WhatsAppAction) -> Unit = { _, _ -> },
    pendingCallAction: CallAction? = null,
    onConfirmCall: (CallAction) -> Unit = {},
    onCancelCall: () -> Unit = {},
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current
    val clipboardManager = LocalClipboardManager.current
    val haptic = LocalHapticFeedback.current
    val scrollState = rememberScrollState()

    var inputText by remember { mutableStateOf("") }
    var spokenText by remember { mutableStateOf("") }
    var isListening by remember { mutableStateOf(false) }
    var rmsLevel by remember { mutableFloatStateOf(0f) }
    var showThought by remember { mutableStateOf(false) }

    // Auto-scroll when new streaming content arrives
    LaunchedEffect(assistantResponse, thoughtText, isThinking) {
        if (assistantResponse.isNotEmpty() || isThinking) {
            scrollState.animateScrollTo(scrollState.maxValue)
        }
    }

    // Pulsing animation for the glowing assistant orb
    val infiniteTransition = rememberInfiniteTransition(label = "gemini_orb_pulse")
    val breathingScale by infiniteTransition.animateFloat(
        initialValue = 0.94f,
        targetValue = 1.06f,
        animationSpec = infiniteRepeatable(
            animation = tween(1400, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "orb_scale"
    )

    val spinAngle by infiniteTransition.animateFloat(
        initialValue = 0f,
        targetValue = 360f,
        animationSpec = infiniteRepeatable(
            animation = tween(4000, easing = LinearEasing),
            repeatMode = RepeatMode.Restart
        ),
        label = "spin_angle"
    )

    // Setup speech recognizer
    var speechRecognizer by remember { mutableStateOf<SpeechRecognizer?>(null) }
    var keepListening by remember { mutableStateOf(false) }

    fun buildListenIntent() = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
        putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
        putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault())
        putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
        putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
        putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 1800L)
        putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, 1200L)
    }

    fun startListening() {
        if (!SpeechRecognizer.isRecognitionAvailable(context)) return
        keepListening = true
        try {
            speechRecognizer?.destroy()
            val recognizer = SpeechRecognizer.createSpeechRecognizer(context)
            speechRecognizer = recognizer

            recognizer.setRecognitionListener(object : RecognitionListener {
                override fun onReadyForSpeech(params: Bundle?) {
                    isListening = true
                }

                override fun onBeginningOfSpeech() {}

                override fun onRmsChanged(rmsdB: Float) {
                    rmsLevel = (rmsdB / 10f).coerceIn(0f, 1f)
                }

                override fun onBufferReceived(buffer: ByteArray?) {}

                override fun onEndOfSpeech() {}

                override fun onError(error: Int) {
                    isListening = false
                    rmsLevel = 0f
                    val shouldRestart = keepListening && error in listOf(
                        SpeechRecognizer.ERROR_SPEECH_TIMEOUT,
                        SpeechRecognizer.ERROR_NO_MATCH,
                        SpeechRecognizer.ERROR_RECOGNIZER_BUSY
                    )
                    if (shouldRestart) {
                        try {
                            speechRecognizer?.destroy()
                            val newRecognizer = SpeechRecognizer.createSpeechRecognizer(context)
                            speechRecognizer = newRecognizer
                            newRecognizer.setRecognitionListener(this)
                            newRecognizer.startListening(buildListenIntent())
                            isListening = true
                        } catch (_: Exception) {}
                    }
                }

                override fun onResults(results: Bundle?) {
                    isListening = false
                    rmsLevel = 0f
                    val matches = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                    val text = matches?.firstOrNull()?.trim()
                    if (!text.isNullOrBlank()) {
                        spokenText = text
                        inputText = text

                        val lower = text.lowercase(Locale.getDefault())
                        val isAffirmative = lower in listOf(
                            "yes", "yeah", "yep", "sure", "send", "send it", "call", "call now",
                            "call him", "call her", "confirm", "okay", "ok", "avunu", "chey", "pampu", "sare"
                        ) || lower.startsWith("yes") || lower.startsWith("send") || lower.startsWith("call") || lower.startsWith("avunu")

                        val isNegative = lower in listOf(
                            "no", "nope", "cancel", "stop", "vadhu", "don't send", "dont", "oddu"
                        ) || lower.startsWith("no") || lower.startsWith("cancel") || lower.startsWith("vadhu")

                        if (pendingWhatsAppAction != null && pendingWhatsAppAction.status == WhatsAppStatus.AWAITING_CONFIRMATION) {
                            if (isAffirmative) {
                                onConfirmWhatsAppSend(pendingWhatsAppAction)
                                return
                            } else if (isNegative) {
                                onCancelWhatsAppAction()
                                return
                            }
                        } else if (pendingCallAction != null && pendingCallAction.status == CallStatus.AWAITING_CONFIRMATION) {
                            if (isAffirmative) {
                                onConfirmCall(pendingCallAction)
                                return
                            } else if (isNegative) {
                                onCancelCall()
                                return
                            }
                        }

                        // Check intents
                        val waIntent = WhatsAppActionHandler.parseWhatsAppIntent(text)
                        val smsIntent = SmsActionHandler.parseMessageIntent(text)
                        val callTarget = CallActionHandler.parseCallIntent(text)
                        when {
                            waIntent != null -> onMessageSend(waIntent.first, waIntent.second, MessagePlatform.WHATSAPP)
                            smsIntent != null -> onMessageSend(smsIntent.first, smsIntent.second, MessagePlatform.BACKGROUND_SMS)
                            callTarget != null -> onCallContact(callTarget)
                            else -> onSubmitPrompt(text)
                        }
                    }
                }

                override fun onPartialResults(partialResults: Bundle?) {
                    val matches = partialResults?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                    val text = matches?.firstOrNull()
                    if (!text.isNullOrBlank()) {
                        spokenText = text
                        inputText = text
                    }
                }

                override fun onEvent(eventType: Int, params: Bundle?) {}
            })

            recognizer.startListening(buildListenIntent())
            isListening = true
        } catch (_: Exception) {
            isListening = false
            keepListening = false
        }
    }

    fun stopListening() {
        keepListening = false
        try { speechRecognizer?.stopListening() } catch (_: Exception) {}
        try { speechRecognizer?.destroy() } catch (_: Exception) {}
        speechRecognizer = null
        isListening = false
        rmsLevel = 0f
    }

    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) {
            startListening()
        }
    }

    fun requestAndListen() {
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
            if (isListening) stopListening() else startListening()
        } else {
            permissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
        }
    }

    // Auto-listen when assistant sheet opens if no active conversation exists
    LaunchedEffect(Unit) {
        if (userQuery.isBlank() && assistantResponse.isBlank()) {
            if (ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
                startListening()
            }
        }
    }

    // Auto-listen when assistant finishes speaking a confirmation prompt ("Would you like to call...?", etc.)
    LaunchedEffect(isSpeaking) {
        if (!isSpeaking && (pendingCallAction?.status == CallStatus.AWAITING_CONFIRMATION || pendingWhatsAppAction?.status == WhatsAppStatus.AWAITING_CONFIRMATION)) {
            kotlinx.coroutines.delay(300)
            if (ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
                startListening()
            }
        }
    }

    DisposableEffect(Unit) {
        onDispose {
            keepListening = false
            try { speechRecognizer?.stopListening() } catch (_: Exception) {}
            try { speechRecognizer?.destroy() } catch (_: Exception) {}
        }
    }

    // Scrim + Animated Gemini Bottom Sheet
    Box(
        modifier = modifier
            .fillMaxSize()
            .background(Color.Black.copy(alpha = 0.55f))
            .clickable(
                interactionSource = remember { MutableInteractionSource() },
                indication = null
            ) { onDismiss() }
    ) {
        // Multi-color ambient background aura at the bottom
        Box(
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .fillMaxWidth()
                .fillMaxHeight(if (userQuery.isNotBlank() || assistantResponse.isNotBlank()) 0.88f else 0.52f)
                .background(
                    Brush.verticalGradient(
                        colors = listOf(
                            Color.Transparent,
                            GeminiBlue.copy(alpha = 0.25f),
                            GeminiPurple.copy(alpha = 0.20f)
                        )
                    )
                )
        )

        Surface(
            shape = RoundedCornerShape(topStart = 28.dp, topEnd = 28.dp),
            color = Color(0xFF1E1F22),
            shadowElevation = 24.dp,
            border = BorderStroke(1.dp, GeminiGradient),
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .fillMaxWidth()
                .fillMaxHeight(if (userQuery.isNotBlank() || assistantResponse.isNotBlank()) 0.85f else 0.48f)
                .clickable(
                    interactionSource = remember { MutableInteractionSource() },
                    indication = null
                ) { /* consume */ }
        ) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(bottom = 16.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                // ── Top Bar with Handle & Gemini Header ─────────────────────
                Box(
                    modifier = Modifier
                        .padding(top = 10.dp, bottom = 4.dp)
                        .size(width = 36.dp, height = 4.dp)
                        .clip(RoundedCornerShape(2.dp))
                        .background(Color(0xFF5F6368))
                )

                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 20.dp, vertical = 6.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    // Left: Gemini rainbow sparkle badge + Brand
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Surface(
                            shape = CircleShape,
                            color = Color(0xFF2B2C30),
                            border = BorderStroke(1.2.dp, GeminiGradient),
                            modifier = Modifier.size(28.dp)
                        ) {
                            Box(contentAlignment = Alignment.Center) {
                                Icon(
                                    imageVector = Icons.Default.AutoAwesome,
                                    contentDescription = null,
                                    tint = GeminiBlue,
                                    modifier = Modifier
                                        .size(16.dp)
                                        .rotate(spinAngle)
                                )
                            }
                        }
                        Text(
                            text = "Gemma",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                            color = Color.White
                        )
                    }

                    // Right: "Open in Gemma" Pill + Close
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        // Gemini-style "Open in app" pill button
                        Surface(
                            shape = RoundedCornerShape(16.dp),
                            color = Color(0xFF2E3134),
                            border = BorderStroke(1.dp, Color(0xFF444746)),
                            modifier = Modifier.clickable {
                                stopListening()
                                onOpenInApp()
                            }
                        ) {
                            Row(
                                modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(4.dp)
                            ) {
                                Icon(
                                    imageVector = Icons.Default.OpenInFull,
                                    contentDescription = "Open in Gemma app",
                                    tint = Color(0xFFC4C7C5),
                                    modifier = Modifier.size(14.dp)
                                )
                                Text(
                                    text = "Open in app",
                                    color = Color(0xFFE3E3E3),
                                    fontSize = 12.sp,
                                    fontWeight = FontWeight.Medium
                                )
                            }
                        }

                        IconButton(
                            onClick = {
                                stopListening()
                                onDismiss()
                            },
                            modifier = Modifier.size(32.dp)
                        ) {
                            Icon(
                                imageVector = Icons.Default.Close,
                                contentDescription = "Close",
                                tint = Color(0xFF9AA0A6),
                                modifier = Modifier.size(20.dp)
                            )
                        }
                    }
                }

                HorizontalDivider(
                    color = Color(0xFF333538),
                    thickness = 0.5.dp,
                    modifier = Modifier.padding(vertical = 4.dp)
                )

                // ── Main Content Area (Scrollable Conversation or Voice Orb) ─
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .fillMaxWidth()
                        .padding(horizontal = 18.dp)
                ) {
                    if (pendingWhatsAppAction != null) {
                        Box(modifier = Modifier.padding(vertical = 4.dp)) {
                            WhatsAppActionCard(
                                action = pendingWhatsAppAction,
                                onConfirmSend = onConfirmWhatsAppSend,
                                onCancel = { onCancelWhatsAppAction() },
                                onSelectCandidate = onSelectWhatsAppCandidate,
                                onPlatformChanged = onPlatformChanged
                            )
                        }
                    } else if (pendingCallAction != null) {
                        Box(modifier = Modifier.padding(vertical = 4.dp)) {
                            CallActionCard(
                                action = pendingCallAction,
                                onCallNow = onConfirmCall,
                                onCancel = { onCancelCall() }
                            )
                        }
                    } else if (userQuery.isNotBlank() || assistantResponse.isNotBlank() || isThinking) {
                        // Conversation turn view
                        Column(
                            modifier = Modifier
                                .fillMaxSize()
                                .verticalScroll(scrollState),
                            verticalArrangement = Arrangement.spacedBy(12.dp)
                        ) {
                            // User Query Bubble
                            if (userQuery.isNotBlank()) {
                                Row(
                                    modifier = Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.End
                                ) {
                                    Surface(
                                        shape = RoundedCornerShape(20.dp),
                                        color = Color(0xFF2D2F34),
                                        border = BorderStroke(1.dp, Color(0xFF3E4146)),
                                        modifier = Modifier.widthIn(max = 320.dp)
                                    ) {
                                        Text(
                                            text = userQuery,
                                            style = MaterialTheme.typography.bodyMedium,
                                            color = Color.White,
                                            modifier = Modifier.padding(horizontal = 16.dp, vertical = 10.dp)
                                        )
                                    }
                                }
                            }

                            // Thinking Indicator
                            if (isThinking && assistantResponse.isBlank()) {
                                Row(
                                    verticalAlignment = Alignment.CenterVertically,
                                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                                    modifier = Modifier.padding(top = 8.dp)
                                ) {
                                    Surface(
                                        shape = CircleShape,
                                        color = Color(0xFF303134),
                                        border = BorderStroke(1.5.dp, GeminiGradient),
                                        modifier = Modifier.size(24.dp)
                                    ) {
                                        Box(contentAlignment = Alignment.Center) {
                                            Icon(
                                                imageVector = Icons.Default.AutoAwesome,
                                                contentDescription = null,
                                                tint = GeminiBlue,
                                                modifier = Modifier
                                                    .size(14.dp)
                                                    .rotate(spinAngle)
                                            )
                                        }
                                    }
                                    Text(
                                        text = "Thinking with Gemma…",
                                        style = MaterialTheme.typography.bodyMedium,
                                        color = Color(0xFF9AA0A6),
                                        fontWeight = FontWeight.Medium
                                    )
                                }
                            }

                            // Thought process toggle (if available)
                            if (thoughtText.isNotBlank()) {
                                Surface(
                                    shape = RoundedCornerShape(12.dp),
                                    color = Color(0xFF26272B),
                                    border = BorderStroke(1.dp, Color(0xFF3A3B40)),
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .clickable { showThought = !showThought }
                                ) {
                                    Column(modifier = Modifier.padding(10.dp)) {
                                        Row(
                                            verticalAlignment = Alignment.CenterVertically,
                                            horizontalArrangement = Arrangement.SpaceBetween,
                                            modifier = Modifier.fillMaxWidth()
                                        ) {
                                            Text(
                                                text = "Thought process",
                                                color = Color(0xFF8AB4F8),
                                                fontSize = 12.sp,
                                                fontWeight = FontWeight.SemiBold
                                            )
                                            Icon(
                                                imageVector = if (showThought) Icons.Default.KeyboardArrowUp else Icons.Default.KeyboardArrowDown,
                                                contentDescription = null,
                                                tint = Color(0xFF8AB4F8),
                                                modifier = Modifier.size(16.dp)
                                            )
                                        }
                                        if (showThought) {
                                            Spacer(modifier = Modifier.height(6.dp))
                                            Text(
                                                text = thoughtText,
                                                color = Color(0xFFBDC1C6),
                                                fontSize = 12.sp,
                                                lineHeight = 16.sp
                                            )
                                        }
                                    }
                                }
                            }

                            // Assistant Streaming Response with Markdown
                            if (assistantResponse.isNotBlank()) {
                                Surface(
                                    shape = RoundedCornerShape(16.dp),
                                    color = Color(0xFF28292D),
                                    modifier = Modifier.fillMaxWidth()
                                ) {
                                    Column(modifier = Modifier.padding(14.dp)) {
                                        MarkdownText(
                                            text = assistantResponse,
                                            isUser = false,
                                            overrideTextColor = Color(0xFFE8EAED)
                                        )

                                        Spacer(modifier = Modifier.height(8.dp))

                                        // Assistant Action Buttons: Speaker (TTS) & Copy
                                        Row(
                                            modifier = Modifier.fillMaxWidth(),
                                            horizontalArrangement = Arrangement.End,
                                            verticalAlignment = Alignment.CenterVertically
                                        ) {
                                            // TTS Voice Button
                                            IconButton(
                                                onClick = { onToggleSpeak() },
                                                modifier = Modifier.size(32.dp)
                                            ) {
                                                Icon(
                                                    imageVector = if (isSpeaking) Icons.Default.VolumeUp else Icons.Default.VolumeDown,
                                                    contentDescription = "Read aloud",
                                                    tint = if (isSpeaking) GeminiBlue else Color(0xFF9AA0A6),
                                                    modifier = Modifier.size(18.dp)
                                                )
                                            }

                                            // Copy Button
                                            IconButton(
                                                onClick = {
                                                    clipboardManager.setText(AnnotatedString(assistantResponse))
                                                    haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                                                    Toast.makeText(context, "Copied to clipboard", Toast.LENGTH_SHORT).show()
                                                },
                                                modifier = Modifier.size(32.dp)
                                            ) {
                                                Icon(
                                                    imageVector = Icons.Default.ContentCopy,
                                                    contentDescription = "Copy response",
                                                    tint = Color(0xFF9AA0A6),
                                                    modifier = Modifier.size(16.dp)
                                                )
                                            }
                                        }
                                    }
                                }
                            }

                            Spacer(modifier = Modifier.height(10.dp))
                        }
                    } else {
                        // Empty state: Central Voice Orb
                        val activeScale = if (isListening) (0.92f + rmsLevel * 0.28f) else breathingScale

                        Column(
                            modifier = Modifier.fillMaxSize(),
                            horizontalAlignment = Alignment.CenterHorizontally,
                            verticalArrangement = Arrangement.Center
                        ) {
                            Box(
                                contentAlignment = Alignment.Center,
                                modifier = Modifier
                                    .size(86.dp)
                                    .clip(CircleShape)
                                    .background(
                                        Brush.radialGradient(
                                            colors = if (isListening)
                                                listOf(GeminiBlue.copy(alpha = 0.35f), Color.Transparent)
                                            else
                                                listOf(Color(0xFF2A2B2E), Color.Transparent)
                                        )
                                    )
                                    .scale(activeScale)
                                    .clickable { requestAndListen() }
                            ) {
                                Surface(
                                    shape = CircleShape,
                                    color = Color(0xFF303134),
                                    border = BorderStroke(
                                        2.dp,
                                        if (isListening) GeminiGradient
                                        else Brush.linearGradient(listOf(Color(0xFF5F6368), Color(0xFF5F6368)))
                                    ),
                                    modifier = Modifier.size(62.dp)
                                ) {
                                    Box(contentAlignment = Alignment.Center) {
                                        if (isListening) {
                                            Row(
                                                horizontalArrangement = Arrangement.spacedBy(3.dp),
                                                verticalAlignment = Alignment.CenterVertically,
                                                modifier = Modifier.height(28.dp)
                                            ) {
                                                val waveColors = listOf(GeminiBlue, GeminiPurple, GeminiRed, GeminiYellow, GeminiGreen)
                                                waveColors.forEachIndexed { idx, barColor ->
                                                    val factor = when (idx) {
                                                        0, 4 -> 0.45f
                                                        1, 3 -> 0.75f
                                                        else -> 1.0f
                                                    }
                                                    val dynamicHeight = (8.dp + (22.dp * (rmsLevel * factor).coerceIn(0f, 1f)))
                                                    Box(
                                                        modifier = Modifier
                                                            .width(3.5.dp)
                                                            .height(dynamicHeight)
                                                            .clip(RoundedCornerShape(2.dp))
                                                            .background(barColor)
                                                    )
                                                }
                                            }
                                        } else {
                                            Icon(
                                                imageVector = Icons.Default.Mic,
                                                contentDescription = null,
                                                tint = Color(0xFF9AA0A6),
                                                modifier = Modifier.size(28.dp)
                                            )
                                        }
                                    }
                                }
                            }

                            Spacer(modifier = Modifier.height(12.dp))

                            Text(
                                text = when {
                                    isListening && spokenText.isNotBlank() -> spokenText
                                    isListening -> "Listening…"
                                    spokenText.isNotBlank() -> spokenText
                                    else -> "Ask anything or say \"Hey Gemma\""
                                },
                                style = MaterialTheme.typography.bodyMedium,
                                color = if (isListening) Color(0xFFE8EAED) else Color(0xFF9AA0A6),
                                textAlign = TextAlign.Center,
                                maxLines = 2,
                                modifier = Modifier.padding(horizontal = 24.dp)
                            )
                        }
                    }
                }

                Spacer(modifier = Modifier.height(10.dp))

                // ── Bottom Input Row ─────────────────────────────────────────
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    OutlinedTextField(
                        value = inputText,
                        onValueChange = { inputText = it },
                        placeholder = {
                            Text(
                                "Ask Gemma anything…",
                                color = Color(0xFF6E7278),
                                fontSize = 14.sp
                            )
                        },
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedContainerColor = Color(0xFF2A2B2E),
                            unfocusedContainerColor = Color(0xFF2A2B2E),
                            focusedBorderColor = GeminiBlue.copy(alpha = 0.7f),
                            unfocusedBorderColor = Color(0xFF3C4043),
                            focusedTextColor = Color.White,
                            unfocusedTextColor = Color.White
                        ),
                        shape = RoundedCornerShape(26.dp),
                        modifier = Modifier.weight(1f),
                        singleLine = true,
                        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
                        keyboardActions = KeyboardActions(
                            onSend = {
                                if (inputText.isNotBlank()) {
                                    stopListening()
                                    val submitted = inputText.trim()
                                    inputText = ""
                                    val waIntent = WhatsAppActionHandler.parseWhatsAppIntent(submitted)
                                    val smsIntent = SmsActionHandler.parseMessageIntent(submitted)
                                    val callTarget = CallActionHandler.parseCallIntent(submitted)
                                    when {
                                        waIntent != null -> onMessageSend(waIntent.first, waIntent.second, MessagePlatform.WHATSAPP)
                                        smsIntent != null -> onMessageSend(smsIntent.first, smsIntent.second, MessagePlatform.BACKGROUND_SMS)
                                        callTarget != null -> onCallContact(callTarget)
                                        else -> onSubmitPrompt(submitted)
                                    }
                                }
                            }
                        )
                    )

                    Spacer(modifier = Modifier.width(8.dp))

                    // Mic / Send dynamic action button
                    Box(
                        contentAlignment = Alignment.Center,
                        modifier = Modifier
                            .size(46.dp)
                            .clip(CircleShape)
                            .background(
                                if (inputText.isNotBlank() || isStreaming)
                                    Brush.linearGradient(listOf(GeminiBlue, GeminiPurple))
                                else if (isListening)
                                    GeminiGradient
                                else
                                    Brush.linearGradient(listOf(Color(0xFF303134), Color(0xFF303134)))
                            )
                            .clickable {
                                if (isStreaming) {
                                    onStopGeneration()
                                } else if (inputText.isNotBlank()) {
                                    stopListening()
                                    val submitted = inputText.trim()
                                    inputText = ""
                                    val waIntent = WhatsAppActionHandler.parseWhatsAppIntent(submitted)
                                    val smsIntent = SmsActionHandler.parseMessageIntent(submitted)
                                    val callTarget = CallActionHandler.parseCallIntent(submitted)
                                    when {
                                        waIntent != null -> onMessageSend(waIntent.first, waIntent.second, MessagePlatform.WHATSAPP)
                                        smsIntent != null -> onMessageSend(smsIntent.first, smsIntent.second, MessagePlatform.BACKGROUND_SMS)
                                        callTarget != null -> onCallContact(callTarget)
                                        else -> onSubmitPrompt(submitted)
                                    }
                                } else {
                                    requestAndListen()
                                }
                            }
                    ) {
                        Icon(
                            imageVector = when {
                                isStreaming -> Icons.Default.Stop
                                inputText.isNotBlank() -> Icons.Default.Send
                                isListening -> Icons.Default.Mic
                                else -> Icons.Default.Mic
                            },
                            contentDescription = "Action",
                            tint = if (inputText.isNotBlank() || isListening || isStreaming) Color.White else Color(0xFF9AA0A6),
                            modifier = Modifier.size(20.dp)
                        )
                    }
                }

                Spacer(modifier = Modifier.height(8.dp))

                // ── Bottom Gemini rainbow spectrum accent line ──────────────
                Box(
                    modifier = Modifier
                        .fillMaxWidth(0.55f)
                        .height(2.5.dp)
                        .clip(RoundedCornerShape(1.5.dp))
                        .background(GeminiGradient)
                )
            }
        }
    }
}