package com.teja.gemmmobile.assistant

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Send
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

private val WhatsAppGreen = Color(0xFF25D366)
private val WhatsAppDarkGreen = Color(0xFF075E54)
private val WhatsAppTeal = Color(0xFF128C7E)
private val WhatsAppBg = Color(0xFFE8F5E9)

@Composable
fun WhatsAppActionCard(
    action: WhatsAppAction,
    onConfirmSend: (WhatsAppAction) -> Unit = {},
    onCancel: (WhatsAppAction) -> Unit = {},
    onSelectCandidate: (ContactMatch, WhatsAppAction) -> Unit = { _, _ -> },
    onEditMessage: (String, WhatsAppAction) -> Unit = { _, _ -> },
    onSendAgain: (WhatsAppAction) -> Unit = {},
    onOpenA11ySettings: () -> Unit = {},
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current
    val isA11yEnabled = GemmaAccessibilityService.isAccessibilityEnabled(context)
    var isEditing by remember { mutableStateOf(false) }
    var currentText by remember(action.messageText) { mutableStateOf(action.messageText) }

    Surface(
        shape = RoundedCornerShape(16.dp),
        color = Color(0xFFF9FBF9),
        border = BorderStroke(1.dp, WhatsAppGreen.copy(alpha = 0.35f)),
        shadowElevation = 2.dp,
        modifier = modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(14.dp)
        ) {
            // Header: WhatsApp Icon & Badge
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Surface(
                        shape = CircleShape,
                        color = WhatsAppGreen,
                        modifier = Modifier.size(26.dp)
                    ) {
                        Box(contentAlignment = Alignment.Center) {
                            Text(
                                text = "W",
                                color = Color.White,
                                fontWeight = FontWeight.Bold,
                                fontSize = 14.sp
                            )
                        }
                    }
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "WhatsApp Direct Action",
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.Bold,
                        color = WhatsAppDarkGreen
                    )
                }

                // Status Pill
                StatusChip(status = action.status)
            }

            Spacer(modifier = Modifier.height(10.dp))

            // Contact Info Row
            Surface(
                shape = RoundedCornerShape(10.dp),
                color = Color.White,
                border = BorderStroke(0.5.dp, Color(0xFFE0E0E0)),
                modifier = Modifier.fillMaxWidth()
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 10.dp, vertical = 8.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Surface(
                        shape = CircleShape,
                        color = WhatsAppBg,
                        modifier = Modifier.size(32.dp)
                    ) {
                        Box(contentAlignment = Alignment.Center) {
                            Icon(
                                imageVector = Icons.Default.Person,
                                contentDescription = null,
                                tint = WhatsAppTeal,
                                modifier = Modifier.size(18.dp)
                            )
                        }
                    }
                    Spacer(modifier = Modifier.width(10.dp))
                    Column {
                        Text(
                            text = action.recipientName,
                            style = MaterialTheme.typography.bodyMedium,
                            fontWeight = FontWeight.SemiBold,
                            color = Color(0xFF1E1E1E)
                        )
                        val subText = action.matchedNumber ?: "No contact number found"
                        Text(
                            text = subText,
                            style = MaterialTheme.typography.labelSmall,
                            color = if (action.matchedNumber != null) Color(0xFF6B6B6B) else MaterialTheme.colorScheme.error
                        )
                    }
                }
            }

            // Multiple candidate chips if available
            if (action.status == WhatsAppStatus.AWAITING_CONFIRMATION && action.candidateContacts.size > 1) {
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = "Multiple matches found. Tap to select:",
                    style = MaterialTheme.typography.labelSmall,
                    color = Color(0xFF666666),
                    fontWeight = FontWeight.Medium
                )
                Spacer(modifier = Modifier.height(4.dp))
                LazyRow(
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    items(action.candidateContacts) { candidate ->
                        val isSelected = candidate.phoneNumber == action.matchedNumber
                        Surface(
                            shape = RoundedCornerShape(12.dp),
                            color = if (isSelected) WhatsAppGreen.copy(alpha = 0.15f) else Color(0xFFF0F0F0),
                            border = BorderStroke(1.dp, if (isSelected) WhatsAppGreen else Color(0xFFE0E0E0)),
                            modifier = Modifier
                                .clip(RoundedCornerShape(12.dp))
                                .clickable { onSelectCandidate(candidate, action) }
                        ) {
                            Text(
                                text = "${candidate.name} (${candidate.formattedNumber})",
                                style = MaterialTheme.typography.labelSmall,
                                color = if (isSelected) WhatsAppDarkGreen else Color(0xFF333333),
                                fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal,
                                modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
                            )
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(8.dp))

            // Message Body — tap the edit icon to modify before sending
            Surface(
                shape = RoundedCornerShape(10.dp),
                color = WhatsAppBg.copy(alpha = 0.5f),
                border = BorderStroke(0.5.dp, WhatsAppGreen.copy(alpha = 0.2f)),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text(
                            text = "Message:",
                            style = MaterialTheme.typography.labelSmall,
                            fontWeight = FontWeight.SemiBold,
                            color = WhatsAppDarkGreen
                        )
                        if (action.status == WhatsAppStatus.AWAITING_CONFIRMATION) {
                            IconButton(
                                onClick = { isEditing = !isEditing },
                                modifier = Modifier.size(22.dp)
                            ) {
                                Icon(
                                    imageVector = if (isEditing) Icons.Default.CheckCircle else Icons.Default.Edit,
                                    contentDescription = if (isEditing) "Done editing" else "Edit message",
                                    tint = WhatsAppTeal,
                                    modifier = Modifier.size(15.dp)
                                )
                            }
                        }
                    }
                    Spacer(modifier = Modifier.height(2.dp))
                    if (isEditing && action.status == WhatsAppStatus.AWAITING_CONFIRMATION) {
                        OutlinedTextField(
                            value = currentText,
                            onValueChange = { currentText = it },
                            modifier = Modifier.fillMaxWidth(),
                            textStyle = MaterialTheme.typography.bodyMedium,
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedBorderColor = WhatsAppGreen,
                                unfocusedBorderColor = WhatsAppGreen.copy(alpha = 0.4f)
                            ),
                            maxLines = 5,
                            shape = RoundedCornerShape(8.dp)
                        )
                    } else {
                        Text(
                            text = "\"$currentText\"",
                            style = MaterialTheme.typography.bodyMedium,
                            fontStyle = FontStyle.Italic,
                            color = Color(0xFF2E2E2E)
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(10.dp))


            // Action Buttons
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.End,
                verticalAlignment = Alignment.CenterVertically
            ) {
                if (action.status == WhatsAppStatus.AWAITING_CONFIRMATION) {
                    OutlinedButton(
                        onClick = { onCancel(action) },
                        shape = RoundedCornerShape(20.dp),
                        contentPadding = PaddingValues(horizontal = 12.dp, vertical = 6.dp),
                        border = BorderStroke(1.dp, Color(0xFFCCCCCC))
                    ) {
                        Icon(
                            imageVector = Icons.Default.Close,
                            contentDescription = null,
                            tint = Color(0xFF757575),
                            modifier = Modifier.size(13.dp)
                        )
                        Spacer(modifier = Modifier.width(4.dp))
                        Text(
                            text = "Cancel",
                            style = MaterialTheme.typography.labelMedium,
                            color = Color(0xFF616161)
                        )
                    }

                    Spacer(modifier = Modifier.width(8.dp))

                    Button(
                        onClick = {
                            isEditing = false
                            onConfirmSend(action.copy(messageText = currentText))
                        },
                        colors = ButtonDefaults.buttonColors(
                            containerColor = WhatsAppGreen,
                            contentColor = Color.White
                        ),
                        shape = RoundedCornerShape(20.dp),
                        contentPadding = PaddingValues(horizontal = 14.dp, vertical = 6.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.CheckCircle,
                            contentDescription = null,
                            modifier = Modifier.size(15.dp)
                        )
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(
                            text = "Send on WhatsApp",
                            style = MaterialTheme.typography.labelMedium,
                            fontWeight = FontWeight.Bold
                        )
                    }
                } else if (action.status == WhatsAppStatus.SENT_DIRECTLY) {
                    Button(
                        onClick = { onSendAgain(action) },
                        colors = ButtonDefaults.buttonColors(
                            containerColor = WhatsAppGreen,
                            contentColor = Color.White
                        ),
                        shape = RoundedCornerShape(20.dp),
                        contentPadding = PaddingValues(horizontal = 14.dp, vertical = 6.dp)
                    ) {
                        Icon(
                            imageVector = Icons.Default.Send,
                            contentDescription = null,
                            modifier = Modifier.size(14.dp)
                        )
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(
                            text = "Send Again",
                            style = MaterialTheme.typography.labelMedium,
                            fontWeight = FontWeight.Bold
                        )
                    }
                }
            }

            // Accessibility Helper if not enabled
            if (!isA11yEnabled && action.matchedNumber != null) {
                Spacer(modifier = Modifier.height(8.dp))
                Surface(
                    shape = RoundedCornerShape(8.dp),
                    color = Color(0xFFFFF8E1),
                    border = BorderStroke(0.5.dp, Color(0xFFFFD54F)),
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(8.dp))
                        .clickable { onOpenA11ySettings() }
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 8.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            imageVector = Icons.Default.Settings,
                            contentDescription = null,
                            tint = Color(0xFFF57F17),
                            modifier = Modifier.size(16.dp)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = "Tap to enable 1-Tap Background Auto-Send",
                            style = MaterialTheme.typography.labelSmall,
                            fontWeight = FontWeight.Medium,
                            color = Color(0xFFE65100)
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun StatusChip(status: WhatsAppStatus) {
    val (label, bg, fg, icon) = when (status) {
        WhatsAppStatus.AWAITING_CONFIRMATION -> Quad(
            "Confirm to Send",
            Color(0xFFFFF3E0),
            Color(0xFFE65100),
            Icons.Default.Warning
        )
        WhatsAppStatus.CONFIRMED -> Quad(
            "Confirmed",
            Color(0xFFE8F5E9),
            Color(0xFF2E7D32),
            Icons.Default.CheckCircle
        )
        WhatsAppStatus.SENT_DIRECTLY -> Quad(
            "Sent in Background",
            Color(0xFFE8F5E9),
            Color(0xFF2E7D32),
            Icons.Default.CheckCircle
        )
        WhatsAppStatus.SENDING -> Quad(
            "Sending...",
            Color(0xFFE3F2FD),
            Color(0xFF1565C0),
            null
        )
        WhatsAppStatus.READY_TO_SEND -> Quad(
            "Ready",
            Color(0xFFEDE7F6),
            Color(0xFF4527A0),
            Icons.Default.Send
        )
        WhatsAppStatus.NO_CONTACT_FOUND -> Quad(
            "Contact Not Found",
            Color(0xFFFFEBEE),
            Color(0xFFC62828),
            Icons.Default.Warning
        )
        WhatsAppStatus.PERMISSION_NEEDED -> Quad(
            "Permission Required",
            Color(0xFFFFEBEE),
            Color(0xFFC62828),
            Icons.Default.Warning
        )
        WhatsAppStatus.CANCELLED -> Quad(
            "Cancelled",
            Color(0xFFF5F5F5),
            Color(0xFF757575),
            null
        )
        WhatsAppStatus.IDLE -> Quad(
            "Draft",
            Color(0xFFF5F5F5),
            Color(0xFF616161),
            null
        )
    }

    Surface(
        shape = RoundedCornerShape(12.dp),
        color = bg
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            if (icon != null) {
                Icon(
                    imageVector = icon,
                    contentDescription = null,
                    tint = fg,
                    modifier = Modifier.size(12.dp)
                )
                Spacer(modifier = Modifier.width(4.dp))
            }
            Text(
                text = label,
                style = MaterialTheme.typography.labelSmall,
                fontWeight = FontWeight.SemiBold,
                color = fg
            )
        }
    }
}

private data class Quad<A, B, C, D>(val first: A, val second: B, val third: C, val fourth: D)
