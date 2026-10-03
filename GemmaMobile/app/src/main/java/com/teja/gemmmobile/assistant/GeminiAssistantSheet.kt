package com.teja.gemmmobile.assistant

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.core.*
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.MicOff
import androidx.compose.material.icons.filled.Send
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
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
        GeminiBlue.copy(alpha = 0.45f),
        GeminiPurple.copy(alpha = 0.25f),
        Color.Transparent
    )
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun GeminiAssistantSheet(
    onDismiss: () -> Unit,
    onSubmitPrompt: (String) -> Unit,
    onWhatsAppSend: (recipient: String, message: String) -> Unit,
    onCallContact: (String) -> Unit = {},
    pendingWhatsAppAction: WhatsAppAction? = null,
    onConfirmWhatsAppSend: (WhatsAppAction) -> Unit = {},
    onCancelWhatsAppAction: () -> Unit = {},
    onSelectWhatsAppCandidate: (ContactMatch, WhatsAppAction) -> Unit = { _, _ -> },
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current
    var inputText by remember { mutableStateOf("") }
    var spokenText by remember { mutableStateOf("") }
    var isListening by remember { mutableStateOf(false) }
    var rmsLevel by remember { mutableFloatStateOf(0f) }

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

    val glowAlpha by infiniteTransition.animateFloat(
        initialValue = 0.4f,
        targetValue = 0.85f,
        animationSpec = infiniteRepeatable(
            animation = tween(1200, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "glow_alpha"
    )

    // Setup speech recognizer — continuous mode (auto-restart on silence/timeout)
    var speechRecognizer by remember { mutableStateOf<SpeechRecognizer?>(null) }
    var keepListening by remember { mutableStateOf(false) }

    fun buildListenIntent() = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
        putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
        putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault())
        putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
        putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
        putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 2000L)
        putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, 1500L)
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

                override fun onEndOfSpeech() {
                    // Don't set isListening=false here — we wait for onResults/onError
                }

                override fun onError(error: Int) {
                    isListening = false
                    rmsLevel = 0f
                    // Restart only for recoverable errors (silence timeout, no match)
                    // ERROR_SPEECH_TIMEOUT = 6, ERROR_NO_MATCH = 7, ERROR_RECOGNIZER_BUSY = 8
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
                        // Check for WhatsApp intent first
                        val waIntent = WhatsAppActionHandler.parseWhatsAppIntent(text)
                        // Then check for call intent
                        val callTarget = CallActionHandler.parseCallIntent(text)
                        when {
                            waIntent != null -> onWhatsAppSend(waIntent.first, waIntent.second)
                            callTarget != null -> onCallContact(callTarget)
                            else -> onSubmitPrompt(text)
                        }
                    }
                    // Auto-restart listening after result
                    if (keepListening) {
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

    // Auto-listen when assistant sheet opens
    LaunchedEffect(Unit) {
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
            startListening()
        }
    }

    DisposableEffect(Unit) {
        onDispose {
            keepListening = false
            try { speechRecognizer?.stopListening() } catch (_: Exception) {}
            try { speechRecognizer?.destroy() } catch (_: Exception) {}
        }
    }


    // Scrim + Compact Gemini-style Bottom Sheet
    Box(
        modifier = modifier
            .fillMaxSize()
            .background(Color.Transparent)
            .clickable(
                interactionSource = remember { MutableInteractionSource() },
                indication = null
            ) { onDismiss() }
    ) {
        Surface(
            shape = RoundedCornerShape(topStart = 24.dp, topEnd = 24.dp),
            color = Color(0xFF202124),
            shadowElevation = 20.dp,
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .fillMaxWidth()
                .clickable(
                    interactionSource = remember { MutableInteractionSource() },
                    indication = null
                ) { /* consume */ }
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(bottom = 20.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                // ── Handle ──────────────────────────────────────────────
                Box(
                    modifier = Modifier
                        .padding(top = 10.dp, bottom = 12.dp)
                        .size(width = 32.dp, height = 4.dp)
                        .clip(RoundedCornerShape(2.dp))
                        .background(Color(0xFF5F6368))
                )

                if (pendingWhatsAppAction != null) {
                    // Show WhatsApp action card compactly
                    Box(modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp)) {
                        WhatsAppActionCard(
                            action = pendingWhatsAppAction,
                            onConfirmSend = onConfirmWhatsAppSend,
                            onCancel = { onCancelWhatsAppAction() },
                            onSelectCandidate = onSelectWhatsAppCandidate
                        )
                    }
                } else {
                    // ── Compact orb ─────────────────────────────────────
                    val activeScale = if (isListening) (0.92f + rmsLevel * 0.2f) else 1f

                    Box(
                        contentAlignment = Alignment.Center,
                        modifier = Modifier
                            .size(72.dp)
                            .clip(CircleShape)
                            .background(
                                Brush.radialGradient(
                                    colors = if (isListening)
                                        listOf(GeminiBlue.copy(alpha = 0.25f), Color.Transparent)
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
                                1.5.dp,
                                if (isListening) GeminiGradient
                                else Brush.linearGradient(listOf(Color(0xFF5F6368), Color(0xFF5F6368)))
                            ),
                            modifier = Modifier.size(52.dp)
                        ) {
                            Box(contentAlignment = Alignment.Center) {
                                Icon(
                                    imageVector = if (isListening) Icons.Default.Mic else Icons.Default.MicOff,
                                    contentDescription = null,
                                    tint = if (isListening) Color(0xFF8AB4F8) else Color(0xFF9AA0A6),
                                    modifier = Modifier.size(24.dp)
                                )
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(10.dp))

                    // ── Status text ──────────────────────────────────────
                    Text(
                        text = when {
                            isListening && spokenText.isNotBlank() -> spokenText
                            isListening -> "Listening…"
                            spokenText.isNotBlank() -> spokenText
                            else -> "Tap mic or type"
                        },
                        style = MaterialTheme.typography.bodyMedium,
                        color = if (isListening) Color(0xFFE8EAED) else Color(0xFF9AA0A6),
                        textAlign = TextAlign.Center,
                        maxLines = 2,
                        modifier = Modifier.padding(horizontal = 32.dp)
                    )
                }

                Spacer(modifier = Modifier.height(14.dp))

                // ── Input row ────────────────────────────────────────────
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
                                color = Color(0xFF5F6368),
                                fontSize = 14.sp
                            )
                        },
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedContainerColor = Color(0xFF303134),
                            unfocusedContainerColor = Color(0xFF303134),
                            focusedBorderColor = GeminiBlue.copy(alpha = 0.6f),
                            unfocusedBorderColor = Color(0xFF3C4043),
                            focusedTextColor = Color.White,
                            unfocusedTextColor = Color.White
                        ),
                        shape = RoundedCornerShape(24.dp),
                        modifier = Modifier.weight(1f),
                        singleLine = true,
                        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
                        keyboardActions = KeyboardActions(
                            onSend = {
                                if (inputText.isNotBlank()) {
                                    val waIntent = WhatsAppActionHandler.parseWhatsAppIntent(inputText)
                                    val callTarget = CallActionHandler.parseCallIntent(inputText)
                                    when {
                                        waIntent != null -> onWhatsAppSend(waIntent.first, waIntent.second)
                                        callTarget != null -> onCallContact(callTarget)
                                        else -> onSubmitPrompt(inputText)
                                    }
                                }
                            }
                        )
                    )

                    Spacer(modifier = Modifier.width(8.dp))

                    Box(
                        contentAlignment = Alignment.Center,
                        modifier = Modifier
                            .size(44.dp)
                            .clip(CircleShape)
                            .background(
                                if (inputText.isNotBlank())
                                    Brush.linearGradient(listOf(GeminiBlue, GeminiPurple))
                                else
                                    Brush.linearGradient(listOf(Color(0xFF303134), Color(0xFF303134)))
                            )
                            .clickable {
                                if (inputText.isNotBlank()) {
                                    val waIntent = WhatsAppActionHandler.parseWhatsAppIntent(inputText)
                                    val callTarget = CallActionHandler.parseCallIntent(inputText)
                                    when {
                                        waIntent != null -> onWhatsAppSend(waIntent.first, waIntent.second)
                                        callTarget != null -> onCallContact(callTarget)
                                        else -> onSubmitPrompt(inputText)
                                    }
                                }
                            }
                    ) {
                        Icon(
                            imageVector = Icons.Default.Send,
                            contentDescription = "Send",
                            tint = if (inputText.isNotBlank()) Color.White else Color(0xFF5F6368),
                            modifier = Modifier.size(18.dp)
                        )
                    }
                }

                Spacer(modifier = Modifier.height(10.dp))

                // ── Bottom Gemini gradient line ───────────────────────────
                Box(
                    modifier = Modifier
                        .fillMaxWidth(0.5f)
                        .height(2.dp)
                        .clip(RoundedCornerShape(1.dp))
                        .background(GeminiGradient)
                )
            }
        }
    }

}