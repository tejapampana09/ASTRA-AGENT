package com.teja.gemmmobile.ui

import androidx.compose.ui.graphics.Color

/**
 * ChatGPT-style authentic appearance themes.
 * Eliminates blurry frosted glass in favor of solid, ultra-clean, high-contrast surfaces.
 */
enum class AppTheme(
    val title: String,
    val subtitle: String,
    val background: Color,
    val surface: Color,
    val userBubble: Color,
    val border: Color,
    val accent: Color
) {
    CHATGPT_DARK(
        title = "ChatGPT Dark",
        subtitle = "Official dark charcoal theme",
        background = Color(0xFF171717),
        surface = Color(0xFF212121),
        userBubble = Color(0xFF2F2F2F),
        border = Color(0xFF2E2E30),
        accent = Color(0xFF10A37F)
    ),
    AMOLED_BLACK(
        title = "Midnight AMOLED",
        subtitle = "Pure deep black for OLED screens",
        background = Color(0xFF000000),
        surface = Color(0xFF141416),
        userBubble = Color(0xFF1F1F24),
        border = Color(0xFF26262A),
        accent = Color(0xFF10A37F)
    ),
    SLATE(
        title = "Obsidian Slate",
        subtitle = "Deep graphite with sky accent",
        background = Color(0xFF0F1115),
        surface = Color(0xFF181A20),
        userBubble = Color(0xFF232630),
        border = Color(0xFF2A2D3A),
        accent = Color(0xFF38BDF8)
    ),
    WARM_BRONZE(
        title = "Warm Bronze",
        subtitle = "Warm charcoal with amber accent",
        background = Color(0xFF171513),
        surface = Color(0xFF211E1A),
        userBubble = Color(0xFF2C2823),
        border = Color(0xFF353029),
        accent = Color(0xFFF59E0B)
    );

    companion object {
        fun fromName(name: String?): AppTheme {
            return entries.firstOrNull { it.name.equals(name, ignoreCase = true) } ?: CHATGPT_DARK
        }
    }
}

val LocalChatTheme = androidx.compose.runtime.staticCompositionLocalOf { AppTheme.CHATGPT_DARK }

