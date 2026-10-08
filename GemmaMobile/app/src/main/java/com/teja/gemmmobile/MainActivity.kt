package com.teja.gemmmobile

import android.content.Intent
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

import androidx.compose.material3.darkColorScheme

// Pure AMOLED ChatGPT Dark color scheme — matching real ChatGPT Android app
private val GemmaColorScheme = darkColorScheme(
    primary           = Color(0xFF10A37F),   // Emerald green
    onPrimary         = Color(0xFFFFFFFF),
    primaryContainer  = Color(0xFF1A382B),
    onPrimaryContainer= Color(0xFFA7F3D0),
    secondary         = Color(0xFFF43F5E),   // ChatGPT Coral/Pink Voice Accent
    onSecondary       = Color(0xFFFFFFFF),
    secondaryContainer= Color(0xFF262626),
    onSecondaryContainer = Color(0xFFFFFFFF),
    surface           = Color(0xFF171717),   // Deep dark surface
    onSurface         = Color(0xFFFFFFFF),   // Crisp white text
    surfaceVariant    = Color(0xFF212121),   // Pill, bubbles, cards
    onSurfaceVariant  = Color(0xFFB4B4B4),   // Secondary light gray
    outline           = Color(0xFF333333),   // Thin dark border
    outlineVariant    = Color(0xFF262626),
    background        = Color(0xFF000000),   // Pure AMOLED Black
    onBackground      = Color(0xFFFFFFFF),
    error             = Color(0xFFEF4444),
    onError           = Color(0xFFFFFFFF),
    errorContainer    = Color(0xFF3B1212),
    onErrorContainer  = Color(0xFFFCA5A5),
)

class MainActivity : ComponentActivity() {

    companion object {
        const val EXTRA_SESSION_ID = "EXTRA_SESSION_ID"
    }

    private val chatViewModel: ChatViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        handleIntent(intent)

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

    override fun onResume() {
        super.onResume()
        // Synchronize sessions created or updated while the Assistant overlay was in use
        chatViewModel.refreshSessions()
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        handleIntent(intent)
    }

    private fun handleIntent(incomingIntent: Intent?) {
        if (incomingIntent == null) return

        val targetSessionId = incomingIntent.getStringExtra(EXTRA_SESSION_ID)
        if (!targetSessionId.isNullOrBlank()) {
            chatViewModel.selectSession(targetSessionId)
        }
    }
}
