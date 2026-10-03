package com.teja.gemmmobile

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.lightColorScheme
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import com.teja.gemmmobile.ui.ChatScreen
import com.teja.gemmmobile.ui.ChatViewModel

// Clean ChatGPT-style color scheme — no gradients, pure whites and grays
private val GemmaColorScheme = lightColorScheme(
    primary           = Color(0xFF10A37F),   // ChatGPT green — send button, active chips
    onPrimary         = Color(0xFFFFFFFF),
    primaryContainer  = Color(0xFFECFDF5),   // Very light green for chips
    onPrimaryContainer= Color(0xFF065F46),
    secondary         = Color(0xFF6B6B6B),
    onSecondary       = Color(0xFFFFFFFF),
    secondaryContainer= Color(0xFFF0F0F0),
    onSecondaryContainer = Color(0xFF1A1A1A),
    surface           = Color(0xFFFFFFFF),   // Pure white surface
    onSurface         = Color(0xFF0D0D0D),   // Near-black text
    surfaceVariant    = Color(0xFFF4F4F4),   // Light gray — user bubbles
    onSurfaceVariant  = Color(0xFF343434),
    outline           = Color(0xFFD9D9D9),   // Thin borders
    outlineVariant    = Color(0xFFEEEEEE),
    background        = Color(0xFFFFFFFF),   // White background
    onBackground      = Color(0xFF0D0D0D),
    error             = Color(0xFFEF4444),
    onError           = Color(0xFFFFFFFF),
    errorContainer    = Color(0xFFFEE2E2),
    onErrorContainer  = Color(0xFF991B1B),
)

class MainActivity : ComponentActivity() {

    private val chatViewModel: ChatViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        // Handle digital assistant trigger (Power button long-press or assistant gesture)
        if (intent?.action == android.content.Intent.ACTION_ASSIST) {
            chatViewModel.openAssistantOverlay()
        }

        // Move task to back on back press so background response generation,
        // conversation state, and model engine are never aborted when closing the chat view
        onBackPressedDispatcher.addCallback(this, object : androidx.activity.OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                moveTaskToBack(true)
            }
        })

        setContent {
            MaterialTheme(colorScheme = GemmaColorScheme) {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    ChatScreen(viewModel = chatViewModel)
                }
            }
        }
    }

    override fun onNewIntent(intent: android.content.Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        if (intent.action == android.content.Intent.ACTION_ASSIST) {
            chatViewModel.openAssistantOverlay()
        }
    }
}
