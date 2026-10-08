package com.teja.gemmmobile.ui

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.provider.Settings
import android.widget.Toast
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Language
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Psychology
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Tune
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import com.teja.gemmmobile.ai.GemmaConfig


/**
 * Dedicated Full-Screen Settings & Parameters Configuration Page.
 * Pure AMOLED (#000000) ChatGPT aesthetic with granular controls for:
 * - Model Generation Parameters (Temperature, Max Output Tokens, Top-P, Top-K)
 * - Chain-of-Thought Reasoning & Thinking Token Budget
 * - System Instructions / Custom Persona
 * - Real-Time Web Search Grounding
 * - Voice Assistant & Hands-Free Wake-Word ("Hey Gemma" / "Hey Teja")
 * - Connected App Gateway (WhatsApp Remote Bridge)
 * - Hardware & On-Device Engine Telemetry
 */
@Composable
fun SettingsScreen(
    currentConfig: GemmaConfig,
    isWebSearchEnabled: Boolean,
    onToggleWebSearch: () -> Unit,
    onApplyConfig: (GemmaConfig) -> Unit,
    onResetDefaults: () -> Unit,
    onBack: () -> Unit
) {
    val context = LocalContext.current
    val haptic = LocalHapticFeedback.current

    // Local mutable state initialized from currentConfig
    var temperature by remember(currentConfig) { mutableFloatStateOf(currentConfig.temperature) }
    var maxTokens by remember(currentConfig) { mutableIntStateOf(currentConfig.maxTokens) }
    var topP by remember(currentConfig) { mutableFloatStateOf(currentConfig.topP) }
    var topK by remember(currentConfig) { mutableIntStateOf(currentConfig.topK) }
    var enableThinking by remember(currentConfig) { mutableStateOf(currentConfig.enableThinking) }
    var thinkingBudget by remember(currentConfig) { mutableIntStateOf(currentConfig.thinkingBudget) }
    var systemPrompt by remember(currentConfig) { mutableStateOf(currentConfig.systemPrompt) }



    // Intercept hardware/gesture back press to return smoothly to Chat
    BackHandler {
        onBack()
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Color(0xFF000000))
            .statusBarsPadding()
            .navigationBarsPadding()
    ) {
        Column(modifier = Modifier.fillMaxSize()) {

            // Top App Bar
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 8.dp, vertical = 10.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    IconButton(
                        onClick = {
                            haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                            onBack()
                        }
                    ) {
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = "Back",
                            tint = Color.White
                        )
                    }
                    Spacer(modifier = Modifier.width(6.dp))
                    Column {
                        Text(
                            text = "Parameters & Config",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                            color = Color.White
                        )
                        Text(
                            text = "Gemma 4 E2B Local Engine",
                            style = MaterialTheme.typography.labelSmall,
                            color = Color(0xFF8E8E93)
                        )
                    }
                }

                // Reset Defaults Quick Action
                IconButton(
                    onClick = {
                        haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                        temperature = GemmaConfig.DEFAULT.temperature
                        maxTokens = GemmaConfig.DEFAULT.maxTokens
                        topP = GemmaConfig.DEFAULT.topP
                        topK = GemmaConfig.DEFAULT.topK
                        enableThinking = GemmaConfig.DEFAULT.enableThinking
                        thinkingBudget = GemmaConfig.DEFAULT.thinkingBudget
                        systemPrompt = GemmaConfig.DEFAULT.systemPrompt
                        onResetDefaults()
                        Toast.makeText(context, "Reset to default parameters", Toast.LENGTH_SHORT).show()
                    }
                ) {
                    Icon(
                        imageVector = Icons.Default.Refresh,
                        contentDescription = "Reset to defaults",
                        tint = Color(0xFFA0A0A0)
                    )
                }
            }

            // Scrollable Settings Content
            LazyColumn(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth(),
                contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp)
            ) {

                // SECTION 1: Model Generation & Sampling
                item {
                    SettingsSectionHeader(
                        icon = Icons.Default.Tune,
                        title = "Model & Generation Parameters"
                    )
                }

                item {
                    SettingsCard {
                        // 1. Temperature
                        Column {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = "Temperature (Creativity)",
                                    fontWeight = FontWeight.SemiBold,
                                    fontSize = 14.sp,
                                    color = Color.White
                                )
                                SettingsBadge(text = String.format("%.2f", temperature))
                            }
                            Text(
                                text = "Lower = precise & factual; Higher = diverse & conversational",
                                fontSize = 11.sp,
                                color = Color(0xFF8E8E93),
                                modifier = Modifier.padding(top = 2.dp, bottom = 8.dp)
                            )
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                                PresetPill(label = "Precise", value = 0.2f, isSelected = (temperature == 0.2f)) { temperature = it }
                                PresetPill(label = "Balanced", value = 0.8f, isSelected = (temperature == 0.8f)) { temperature = it }
                                PresetPill(label = "Creative", value = 1.2f, isSelected = (temperature == 1.2f)) { temperature = it }
                            }
                            Slider(
                                value = temperature,
                                onValueChange = { temperature = it },
                                valueRange = 0.0f..1.5f,
                                steps = 29,
                                colors = chatGptSliderColors()
                            )
                        }

                        SettingsDivider()

                        // 2. Max Output Tokens
                        Column {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = "Max Output Tokens",
                                    fontWeight = FontWeight.SemiBold,
                                    fontSize = 14.sp,
                                    color = Color.White
                                )
                                SettingsBadge(text = "$maxTokens tokens")
                            }
                            Text(
                                text = "Upper limit of generated tokens per answer (including thinking budget)",
                                fontSize = 11.sp,
                                color = Color(0xFF8E8E93),
                                modifier = Modifier.padding(top = 2.dp, bottom = 8.dp)
                            )
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                                PresetPill(label = "1024", value = 1024f, isSelected = (maxTokens == 1024)) { maxTokens = it.toInt() }
                                PresetPill(label = "2048 (Default)", value = 2048f, isSelected = (maxTokens == 2048)) { maxTokens = it.toInt() }
                                PresetPill(label = "4096 (Full)", value = 4096f, isSelected = (maxTokens == 4096)) { maxTokens = it.toInt() }
                            }
                            Slider(
                                value = maxTokens.toFloat(),
                                onValueChange = { maxTokens = (it / 64).toInt() * 64 },
                                valueRange = 256f..4096f,
                                steps = 59,
                                colors = chatGptSliderColors()
                            )
                        }

                        SettingsDivider()

                        // 3. Top-P and Top-K Sampling
                        Column {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = "Sampling (Top-P & Top-K)",
                                    fontWeight = FontWeight.SemiBold,
                                    fontSize = 14.sp,
                                    color = Color.White
                                )
                                SettingsBadge(text = "P: ${String.format("%.2f", topP)} • K: $topK")
                            }
                            Spacer(modifier = Modifier.height(6.dp))
                            Text(text = "Top-P (Nucleus Sampling): ${String.format("%.2f", topP)}", fontSize = 12.sp, color = Color(0xFFD1D1D6))
                            Slider(
                                value = topP,
                                onValueChange = { topP = it },
                                valueRange = 0.1f..1.0f,
                                steps = 17,
                                colors = chatGptSliderColors()
                            )

                            Text(text = "Top-K Candidates: $topK", fontSize = 12.sp, color = Color(0xFFD1D1D6))
                            Slider(
                                value = topK.toFloat(),
                                onValueChange = { topK = it.toInt() },
                                valueRange = 1f..100f,
                                steps = 98,
                                colors = chatGptSliderColors()
                            )
                        }
                    }
                }

                // SECTION 2: Chain-of-Thought Reasoning
                item {
                    SettingsSectionHeader(
                        icon = Icons.Default.Psychology,
                        title = "Reasoning & Deep Thinking"
                    )
                }

                item {
                    SettingsCard {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Column(modifier = Modifier.weight(1f).padding(end = 8.dp)) {
                                Text(
                                    text = "Enable Thinking Process",
                                    fontWeight = FontWeight.SemiBold,
                                    fontSize = 14.sp,
                                    color = Color.White
                                )
                                Text(
                                    text = "Gemma analyzes intermediate steps before outputting the final answer.",
                                    fontSize = 11.sp,
                                    color = Color(0xFF8E8E93)
                                )
                            }
                            Switch(
                                checked = enableThinking,
                                onCheckedChange = { enableThinking = it },
                                colors = chatGptSwitchColors()
                            )
                        }

                        if (enableThinking) {
                            Spacer(modifier = Modifier.height(10.dp))
                            SettingsDivider()
                            Spacer(modifier = Modifier.height(6.dp))

                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = "Thinking Token Budget",
                                    fontWeight = FontWeight.Medium,
                                    fontSize = 13.sp,
                                    color = Color.White
                                )
                                SettingsBadge(text = "$thinkingBudget tokens")
                            }
                            Text(
                                text = "Max tokens allocated to internal reasoning (collapsed in UI)",
                                fontSize = 11.sp,
                                color = Color(0xFF8E8E93),
                                modifier = Modifier.padding(top = 2.dp, bottom = 6.dp)
                            )
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                                PresetPill(label = "256", value = 256f, isSelected = (thinkingBudget == 256)) { thinkingBudget = it.toInt() }
                                PresetPill(label = "512 (Recommended)", value = 512f, isSelected = (thinkingBudget == 512)) { thinkingBudget = it.toInt() }
                                PresetPill(label = "1024", value = 1024f, isSelected = (thinkingBudget == 1024)) { thinkingBudget = it.toInt() }
                            }
                            Slider(
                                value = thinkingBudget.toFloat(),
                                onValueChange = { thinkingBudget = (it / 64).toInt() * 64 },
                                valueRange = 128f..1024f,
                                steps = 13,
                                colors = chatGptSliderColors()
                            )
                        }
                    }
                }

                // SECTION 3: System Persona & Instructions
                item {
                    SettingsSectionHeader(
                        icon = Icons.Default.AutoAwesome,
                        title = "System Instructions & Persona"
                    )
                }

                item {
                    SettingsCard {
                        Text(
                            text = "Custom System Prompt",
                            fontWeight = FontWeight.SemiBold,
                            fontSize = 14.sp,
                            color = Color.White
                        )
                        Text(
                            text = "Define the assistant's tone, instructions, and behavior across all chats.",
                            fontSize = 11.sp,
                            color = Color(0xFF8E8E93),
                            modifier = Modifier.padding(top = 2.dp, bottom = 8.dp)
                        )

                        // Quick persona presets
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(6.dp)
                        ) {
                            Surface(
                                shape = RoundedCornerShape(12.dp),
                                color = Color(0xFF212121),
                                border = BorderStroke(1.dp, Color(0xFF383838)),
                                modifier = Modifier
                                    .clip(RoundedCornerShape(12.dp))
                                    .clickable {
                                        systemPrompt = "You are a concise, high-efficiency assistant. Provide direct, highly structured answers."
                                    }
                            ) {
                                Text("Concise", fontSize = 11.sp, color = Color(0xFFECECEC), modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp))
                            }
                            Surface(
                                shape = RoundedCornerShape(12.dp),
                                color = Color(0xFF212121),
                                border = BorderStroke(1.dp, Color(0xFF383838)),
                                modifier = Modifier
                                    .clip(RoundedCornerShape(12.dp))
                                    .clickable {
                                        systemPrompt = "You are an expert senior software engineer. Write clean, idiomatic, production-ready code with explanations."
                                    }
                            ) {
                                Text("Coding Expert", fontSize = 11.sp, color = Color(0xFFECECEC), modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp))
                            }
                            Surface(
                                shape = RoundedCornerShape(12.dp),
                                color = Color(0xFF212121),
                                border = BorderStroke(1.dp, Color(0xFF383838)),
                                modifier = Modifier
                                    .clip(RoundedCornerShape(12.dp))
                                    .clickable {
                                        systemPrompt = "You are Astra, a helpful and witty personal AI assistant fluent in English and Telugu."
                                    }
                            ) {
                                Text("Astra Telugu", fontSize = 11.sp, color = Color(0xFFECECEC), modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp))
                            }
                        }

                        Spacer(modifier = Modifier.height(8.dp))

                        OutlinedTextField(
                            value = systemPrompt,
                            onValueChange = { systemPrompt = it },
                            modifier = Modifier.fillMaxWidth(),
                            minLines = 3,
                            maxLines = 6,
                            shape = RoundedCornerShape(12.dp),
                            placeholder = { Text("e.g. You are a helpful, accurate AI assistant...", color = Color(0xFF6B6B70), fontSize = 12.sp) },
                            textStyle = MaterialTheme.typography.bodySmall.copy(
                                color = Color.White,
                                fontFamily = FontFamily.Monospace,
                                fontSize = 12.sp
                            ),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedContainerColor = Color(0xFF191919),
                                unfocusedContainerColor = Color(0xFF191919),
                                focusedBorderColor = Color(0xFF10A37F),
                                unfocusedBorderColor = Color(0xFF2E2E2E),
                                cursorColor = Color.White
                            )
                        )
                    }
                }

                // SECTION 4: Real-Time Web Search Grounding
                item {
                    SettingsSectionHeader(
                        icon = Icons.Default.Language,
                        title = "Real-Time Web Grounding"
                    )
                }

                item {
                    SettingsCard {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Column(modifier = Modifier.weight(1f).padding(end = 8.dp)) {
                                Text(
                                    text = "Live Web Search Grounding",
                                    fontWeight = FontWeight.SemiBold,
                                    fontSize = 14.sp,
                                    color = Color.White
                                )
                                Text(
                                    text = "Fetches real-time web results when queries ask for current info, news, or live data.",
                                    fontSize = 11.sp,
                                    color = Color(0xFF8E8E93)
                                )
                            }
                            Switch(
                                checked = isWebSearchEnabled,
                                onCheckedChange = { onToggleWebSearch() },
                                colors = chatGptSwitchColors()
                            )
                        }
                    }
                }



                // SECTION 7: Hardware & Engine Telemetry
                item {
                    SettingsCard {
                        Text(
                            text = "Engine Information",
                            fontWeight = FontWeight.SemiBold,
                            fontSize = 13.sp,
                            color = Color.White
                        )
                        Spacer(modifier = Modifier.height(6.dp))
                        TelemetryRow(label = "Model", value = "Gemma 4 E2B Instruct")
                        TelemetryRow(label = "Runtime", value = "LiteRT-LM (On-Device Native)")
                        TelemetryRow(label = "Hardware Target", value = "CPU + GPU OpenCL Hybrid")
                        TelemetryRow(label = "Privacy Guarantee", value = "100% Offline & Zero Data Leakage")
                    }
                }

                // Bottom spacer for floating apply button
                item {
                    Spacer(modifier = Modifier.height(60.dp))
                }
            }

            // Bottom Floating Save Bar
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(Color(0xFF000000))
                    .padding(horizontal = 16.dp, vertical = 12.dp)
            ) {
                Button(
                    onClick = {
                        haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                        val updated = GemmaConfig(
                            temperature = temperature,
                            maxTokens = maxTokens,
                            topP = topP,
                            topK = topK,
                            enableThinking = enableThinking,
                            thinkingBudget = thinkingBudget,
                            systemPrompt = systemPrompt.trim()
                        )
                        onApplyConfig(updated)
                        Toast.makeText(context, "✅ Configuration saved & applied", Toast.LENGTH_SHORT).show()
                        onBack()
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(48.dp),
                    shape = RoundedCornerShape(24.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = Color.White,
                        contentColor = Color.Black
                    )
                ) {
                    Text(
                        text = "Save & Apply Settings",
                        fontWeight = FontWeight.Bold,
                        fontSize = 15.sp
                    )
                }
            }
        }
    }
}

// -------------------------------------------------------------------------
// Helper Components for ChatGPT Style Settings
// -------------------------------------------------------------------------

@Composable
private fun SettingsSectionHeader(icon: ImageVector, title: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = 10.dp, bottom = 4.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            tint = Color(0xFF10A37F),
            modifier = Modifier.size(17.dp)
        )
        Spacer(modifier = Modifier.width(8.dp))
        Text(
            text = title,
            style = MaterialTheme.typography.titleSmall,
            fontWeight = FontWeight.Bold,
            color = Color(0xFFD1D1D6),
            fontSize = 13.sp
        )
    }
}

@Composable
private fun SettingsCard(content: @Composable () -> Unit) {
    Surface(
        shape = RoundedCornerShape(16.dp),
        color = Color(0xFF171717),
        border = BorderStroke(1.dp, Color(0xFF262626)),
        shadowElevation = 2.dp,
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(
            modifier = Modifier.padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            content()
        }
    }
}

@Composable
private fun SettingsDivider() {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 6.dp)
            .height(0.5.dp)
            .background(Color(0xFF262626))
    )
}

@Composable
private fun SettingsBadge(text: String) {
    Surface(
        shape = RoundedCornerShape(8.dp),
        color = Color(0xFF262626),
        border = BorderStroke(0.5.dp, Color(0xFF383838))
    ) {
        Text(
            text = text,
            fontSize = 11.sp,
            fontWeight = FontWeight.SemiBold,
            color = Color(0xFF10A37F),
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp)
        )
    }
}

@Composable
private fun PresetPill(
    label: String,
    value: Float,
    isSelected: Boolean,
    onSelect: (Float) -> Unit
) {
    Surface(
        shape = RoundedCornerShape(12.dp),
        color = if (isSelected) Color(0xFF10A37F).copy(alpha = 0.2f) else Color(0xFF212121),
        border = BorderStroke(
            1.dp,
            if (isSelected) Color(0xFF10A37F) else Color(0xFF2E2E2E)
        ),
        modifier = Modifier
            .clip(RoundedCornerShape(12.dp))
            .clickable { onSelect(value) }
    ) {
        Text(
            text = label,
            fontSize = 11.sp,
            fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal,
            color = if (isSelected) Color(0xFF10A37F) else Color(0xFFB0B0B0),
            modifier = Modifier.padding(horizontal = 9.dp, vertical = 4.dp)
        )
    }
}

@Composable
private fun TelemetryRow(label: String, value: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 2.dp),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(text = label, fontSize = 11.sp, color = Color(0xFF8E8E93))
        Text(text = value, fontSize = 11.sp, color = Color(0xFFECECEC), fontWeight = FontWeight.Medium)
    }
}

@Composable
private fun chatGptSliderColors() = SliderDefaults.colors(
    thumbColor = Color.White,
    activeTrackColor = Color(0xFF10A37F),
    inactiveTrackColor = Color(0xFF2C2C2E)
)

@Composable
private fun chatGptSwitchColors() = SwitchDefaults.colors(
    checkedThumbColor = Color.White,
    checkedTrackColor = Color(0xFF10A37F),
    uncheckedThumbColor = Color(0xFF8E8E93),
    uncheckedTrackColor = Color(0xFF2C2C2E)
)
