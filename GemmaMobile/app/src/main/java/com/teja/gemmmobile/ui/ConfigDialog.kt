package com.teja.gemmmobile.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Slider
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
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
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.teja.gemmmobile.ai.GemmaConfig

/**
 * Modern, square-boxed Configuration Settings Dialog for Gemma 4 E2B IT.
 */
@Composable
fun ConfigDialog(
    currentConfig: GemmaConfig,
    onDismiss: () -> Unit,
    onApply: (GemmaConfig) -> Unit,
    onResetDefaults: () -> Unit
) {
    var temperature by remember(currentConfig) { mutableFloatStateOf(currentConfig.temperature) }
    var maxTokens by remember(currentConfig) { mutableIntStateOf(currentConfig.maxTokens) }
    var topP by remember(currentConfig) { mutableFloatStateOf(currentConfig.topP) }
    var topK by remember(currentConfig) { mutableIntStateOf(currentConfig.topK) }
    var enableThinking by remember(currentConfig) { mutableStateOf(currentConfig.enableThinking) }
    var thinkingBudget by remember(currentConfig) { mutableIntStateOf(currentConfig.thinkingBudget) }
    var systemPrompt by remember(currentConfig) { mutableStateOf(currentConfig.systemPrompt) }

    val scrollState = rememberScrollState()

    AlertDialog(
        onDismissRequest = onDismiss,
        shape = RoundedCornerShape(8.dp),
        containerColor = MaterialTheme.colorScheme.surface,
        title = {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Column {
                    Text(
                        text = "⚙️ Parameters & Config",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold
                    )
                    Text(
                        text = "Gemma 4 E2B Local Inference Engine",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.outline
                    )
                }
            }
        },
        text = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .verticalScroll(scrollState)
                    .padding(vertical = 4.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                // BOX 1: Temperature & Creativity
                SettingBox(title = "Temperature (Creativity)", badge = String.format("%.2f", temperature)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        PresetChip(label = "Precise", value = 0.2f, current = temperature) { temperature = it }
                        PresetChip(label = "Balanced", value = 0.8f, current = temperature) { temperature = it }
                        PresetChip(label = "Creative", value = 1.2f, current = temperature) { temperature = it }
                    }
                    Spacer(modifier = Modifier.height(6.dp))
                    Slider(
                        value = temperature,
                        onValueChange = { temperature = it },
                        valueRange = 0.0f..1.5f,
                        steps = 29
                    )
                    Text(
                        text = "Lower = exact, factual; Higher = diverse, conversational",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.outline,
                        fontSize = 10.sp
                    )
                }

                // BOX 2: Max Output Tokens
                SettingBox(title = "Max Output Tokens", badge = "$maxTokens tokens") {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        PresetChip(label = "1024", value = 1024f, current = maxTokens.toFloat()) { maxTokens = it.toInt() }
                        PresetChip(label = "2048 (Default)", value = 2048f, current = maxTokens.toFloat()) { maxTokens = it.toInt() }
                        PresetChip(label = "4096 (Full)", value = 4096f, current = maxTokens.toFloat()) { maxTokens = it.toInt() }
                    }
                    Spacer(modifier = Modifier.height(6.dp))
                    Slider(
                        value = maxTokens.toFloat(),
                        onValueChange = { maxTokens = (it / 64).toInt() * 64 },
                        valueRange = 256f..4096f,
                        steps = 59
                    )
                    Text(
                        text = "Upper limit of generated tokens per answer (including thinking budget)",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.outline,
                        fontSize = 10.sp
                    )
                }

                // BOX 3: Thinking & Reasoning Mode
                SettingBox(title = "🧠 Chain-of-Thought Reasoning", badge = if (enableThinking) "$thinkingBudget tokens" else "Disabled") {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "Enable Thinking Process",
                            style = MaterialTheme.typography.bodySmall,
                            fontWeight = FontWeight.Medium
                        )
                        Switch(
                            checked = enableThinking,
                            onCheckedChange = { enableThinking = it }
                        )
                    }

                    if (enableThinking) {
                        Spacer(modifier = Modifier.height(4.dp))
                        Slider(
                            value = thinkingBudget.toFloat(),
                            onValueChange = { thinkingBudget = (it / 64).toInt() * 64 },
                            valueRange = 128f..1024f,
                            steps = 13
                        )
                        Text(
                            text = "Thinking token budget: $thinkingBudget tokens (collapses when complete)",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.outline,
                            fontSize = 10.sp
                        )
                        Spacer(modifier = Modifier.height(2.dp))
                        Text(
                            text = "⚡ Tip: Turn off thinking for instant token generation on mobile CPU!",
                            style = MaterialTheme.typography.labelSmall,
                            color = Color(0xFFFFB74D),
                            fontSize = 10.sp,
                            fontWeight = FontWeight.Medium
                        )
                    } else {
                        Spacer(modifier = Modifier.height(2.dp))
                        Text(
                            text = "🚀 Fast mode active: Model skips hidden reasoning and responds immediately.",
                            style = MaterialTheme.typography.labelSmall,
                            color = Color(0xFF10A37F),
                            fontSize = 10.sp,
                            fontWeight = FontWeight.Medium
                        )
                    }
                }

                // BOX 4: Top-P & Top-K Sampling
                SettingBox(title = "Sampling (Top-P / Top-K)", badge = "P: ${String.format("%.2f", topP)} • K: $topK") {
                    Text(text = "Top-P (Nucleus)", style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.SemiBold)
                    Slider(
                        value = topP,
                        onValueChange = { topP = it },
                        valueRange = 0.1f..1.0f,
                        steps = 17
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(text = "Top-K: $topK", style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.SemiBold)
                    Slider(
                        value = topK.toFloat(),
                        onValueChange = { topK = it.toInt() },
                        valueRange = 1f..100f,
                        steps = 98
                    )
                }

                // BOX 5: System Prompt Box
                SettingBox(title = "System Prompt", badge = "Custom Role") {
                    OutlinedTextField(
                        value = systemPrompt,
                        onValueChange = { systemPrompt = it },
                        modifier = Modifier.fillMaxWidth(),
                        maxLines = 4,
                        shape = RoundedCornerShape(6.dp),
                        placeholder = { Text("Enter system instruction...") },
                        textStyle = MaterialTheme.typography.bodySmall.copy(fontFamily = FontFamily.Monospace, fontSize = 11.sp)
                    )
                }


            }
        },
        confirmButton = {
            Button(
                onClick = {
                    val updated = GemmaConfig(
                        temperature = temperature,
                        maxTokens = maxTokens,
                        topP = topP,
                        topK = topK,
                        enableThinking = enableThinking,
                        thinkingBudget = thinkingBudget,
                        systemPrompt = systemPrompt.trim(),
                        preferredBackend = currentConfig.preferredBackend
                    )
                    onApply(updated)
                    onDismiss()
                },
                shape = RoundedCornerShape(6.dp),
                colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary)
            ) {
                Text("Save & Apply", fontWeight = FontWeight.Bold)
            }
        },
        dismissButton = {
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                TextButton(
                    onClick = {
                        onResetDefaults()
                        onDismiss()
                    },
                    shape = RoundedCornerShape(6.dp)
                ) {
                    Text("Defaults", color = MaterialTheme.colorScheme.outline)
                }
                OutlinedButton(
                    onClick = onDismiss,
                    shape = RoundedCornerShape(6.dp)
                ) {
                    Text("Cancel")
                }
            }
        }
    )
}

/**
 * Clean square container box for each configuration item.
 */
@Composable
private fun SettingBox(
    title: String,
    badge: String,
    content: @Composable () -> Unit
) {
    Surface(
        shape = RoundedCornerShape(6.dp),
        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.35f),
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.6f)),
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(modifier = Modifier.padding(10.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = title,
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.Bold
                )
                Surface(
                    shape = RoundedCornerShape(4.dp),
                    color = MaterialTheme.colorScheme.primary.copy(alpha = 0.12f)
                ) {
                    Text(
                        text = badge,
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp)
                    )
                }
            }
            Spacer(modifier = Modifier.height(8.dp))
            content()
        }
    }
}

/**
 * Clean square preset chip.
 */
@Composable
private fun PresetChip(
    label: String,
    value: Float,
    current: Float,
    onSelect: (Float) -> Unit
) {
    val isSelected = kotlin.math.abs(value - current) < 0.05f
    Surface(
        shape = RoundedCornerShape(4.dp),
        color = if (isSelected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.surface,
        border = BorderStroke(1.dp, if (isSelected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant),
        modifier = Modifier
            .clip(RoundedCornerShape(4.dp))
            .clickable { onSelect(value) }
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.labelSmall,
            fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal,
            color = if (isSelected) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurface,
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
        )
    }
}
