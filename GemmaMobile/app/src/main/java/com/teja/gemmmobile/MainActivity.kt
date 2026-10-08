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

import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.material3.darkColorScheme

// Sleek Translucent Obsidian Dark color scheme — liquid frosted glass aesthetic
private val GemmaColorScheme = darkColorScheme(
    primary           = Color(0xFF10A37F),   // Emerald accent
    onPrimary         = Color(0xFFFFFFFF),
    primaryContainer  = Color(0xFF162D24),
    onPrimaryContainer= Color(0xFFA7F3D0),
    secondary         = Color(0xFFF43F5E),   // Coral accent
    onSecondary       = Color(0xFFFFFFFF),
    secondaryContainer= Color(0xFF1E1E28),
    onSecondaryContainer = Color(0xFFFFFFFF),
    surface           = Color(0xFF121218),   // Deep obsidian surface
    onSurface         = Color(0xFFFFFFFF),   // Crisp white text
    surfaceVariant    = Color(0xFF181822),   // Translucent card base
    onSurfaceVariant  = Color(0xFFB0B0B8),   // Secondary light gray
    outline           = Color(0xFF2C2C38),   // Thin glass border
    outlineVariant    = Color(0xFF20202A),
    background        = Color(0xFF07070A),   // Deep obsidian AMOLED base
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
            val currentTheme by chatViewModel.selectedTheme.collectAsState()
            val colorScheme = androidx.compose.material3.darkColorScheme(
                primary = currentTheme.accent,
                onPrimary = Color.White,
                primaryContainer = currentTheme.surface,
                onPrimaryContainer = Color.White,
                secondary = currentTheme.accent,
                onSecondary = Color.White,
                surface = currentTheme.surface,
                onSurface = Color.White,
                surfaceVariant = currentTheme.userBubble,
                onSurfaceVariant = Color(0xFFC7C7CC),
                background = currentTheme.background,
                onBackground = Color.White,
                outline = currentTheme.border
            )

            androidx.compose.runtime.CompositionLocalProvider(com.teja.gemmmobile.ui.LocalChatTheme provides currentTheme) {
                MaterialTheme(colorScheme = colorScheme) {
                    Surface(
                        modifier = Modifier.fillMaxSize(),
                        color = currentTheme.background
                    ) {
                        ChatScreen(viewModel = chatViewModel)
                    }
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
