package com.teja.gemmmobile.assistant

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Call
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

private val CallBlue = Color(0xFF1A73E8)
private val CallDarkBlue = Color(0xFF0D47A1)
private val CallBg = Color(0xFFE8F0FE)

@Composable
fun CallActionCard(
    action: CallAction,
    onCallNow: (CallAction) -> Unit = {},
    onCancel: (CallAction) -> Unit = {},
    onSelectCandidate: (ContactMatch, CallAction) -> Unit = { _, _ -> },
    modifier: Modifier = Modifier
) {
    Surface(
        shape = RoundedCornerShape(16.dp),
        color = Color(0xFFF9FAFB),
        border = BorderStroke(1.dp, CallBlue.copy(alpha = 0.35f)),
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
            // Header
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Surface(
                        shape = CircleShape,
                        color = CallBlue,
                        modifier = Modifier.size(26.dp)
                    ) {
                        Box(contentAlignment = Alignment.Center) {
                            Icon(
                                imageVector = Icons.Default.Call,
                                contentDescription = null,
                                tint = Color.White,
                                modifier = Modifier.size(15.dp)
                            )
                        }
                    }
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "Phone Call Action",
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.Bold,
                        color = CallDarkBlue
                    )
                }

                // Status Badge
                Surface(
                    shape = RoundedCornerShape(12.dp),
                    color = when (action.status) {
                        CallStatus.AWAITING_CONFIRMATION -> Color(0xFFE3F2FD)
                        CallStatus.DIALED, CallStatus.CALLING -> CallBlue.copy(alpha = 0.15f)
                        CallStatus.NO_CONTACT_FOUND, CallStatus.FAILED -> Color(0xFFFFEBEE)
                        CallStatus.CANCELLED -> Color(0xFFEEEEEE)
                    }
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        if (action.status == CallStatus.NO_CONTACT_FOUND) {
                            Icon(
                                imageVector = Icons.Default.Warning,
                                contentDescription = null,
                                tint = Color(0xFFD32F2F),
                                modifier = Modifier.size(11.dp)
                            )
                            Spacer(modifier = Modifier.width(3.dp))
                        }
                        Text(
                            text = when (action.status) {
                                CallStatus.AWAITING_CONFIRMATION -> "Confirm Call"
                                CallStatus.CALLING -> "Calling..."
                                CallStatus.DIALED -> "Call Placed"
                                CallStatus.NO_CONTACT_FOUND -> "Contact Not Found"
                                CallStatus.FAILED -> "Call Failed"
                                CallStatus.CANCELLED -> "Cancelled"
                            },
                            style = MaterialTheme.typography.labelSmall,
                            fontWeight = FontWeight.SemiBold,
                            color = when (action.status) {
                                CallStatus.AWAITING_CONFIRMATION, CallStatus.CALLING, CallStatus.DIALED -> CallBlue
                                CallStatus.NO_CONTACT_FOUND, CallStatus.FAILED -> Color(0xFFD32F2F)
                                CallStatus.CANCELLED -> Color(0xFF757575)
                            }
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(10.dp))

            // Contact Info
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
                        color = CallBg,
                        modifier = Modifier.size(34.dp)
                    ) {
                        Box(contentAlignment = Alignment.Center) {
                            Icon(
                                imageVector = Icons.Default.Person,
                                contentDescription = null,
                                tint = CallBlue,
                                modifier = Modifier.size(18.dp)
                            )
                        }
                    }
                    Spacer(modifier = Modifier.width(10.dp))
                    Column {
                        Text(
                            text = action.recipientName,
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold,
                            color = Color(0xFF1E1E1E)
                        )
                        Text(
                            text = action.matchedNumber ?: "No phone number",
                            style = MaterialTheme.typography.bodySmall,
                            color = Color(0xFF666666)
                        )
                    }
                }
            }

            // Multiple candidates
            if (action.candidateContacts.size > 1) {
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = "Multiple numbers found. Tap to call:",
                    style = MaterialTheme.typography.labelSmall,
                    color = Color(0xFF777777)
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
                            color = if (isSelected) CallBlue.copy(alpha = 0.15f) else Color(0xFFF0F0F0),
                            border = BorderStroke(1.dp, if (isSelected) CallBlue else Color(0xFFE0E0E0)),
                            modifier = Modifier
                                .clip(RoundedCornerShape(12.dp))
                                .clickable { onSelectCandidate(candidate, action) }
                        ) {
                            Text(
                                text = "${candidate.name} (${candidate.formattedNumber})",
                                style = MaterialTheme.typography.labelSmall,
                                color = if (isSelected) CallDarkBlue else Color(0xFF333333),
                                fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal,
                                modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
                            )
                        }
                    }
                }
            }

            // Call Action Buttons
            if (action.matchedNumber != null) {
                Spacer(modifier = Modifier.height(10.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.End,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    if (action.status == CallStatus.AWAITING_CONFIRMATION) {
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
                            onClick = { onCallNow(action) },
                            colors = ButtonDefaults.buttonColors(containerColor = CallBlue),
                            shape = RoundedCornerShape(20.dp),
                            contentPadding = PaddingValues(horizontal = 14.dp, vertical = 6.dp)
                        ) {
                            Icon(
                                imageVector = Icons.Default.Call,
                                contentDescription = null,
                                tint = Color.White,
                                modifier = Modifier.size(15.dp)
                            )
                            Spacer(modifier = Modifier.width(6.dp))
                            Text(
                                text = "Call",
                                style = MaterialTheme.typography.labelMedium,
                                fontWeight = FontWeight.Bold,
                                color = Color.White
                            )
                        }
                    } else if (action.status == CallStatus.CALLING) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(18.dp),
                            strokeWidth = 2.dp,
                            color = CallBlue
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = "Calling...",
                            style = MaterialTheme.typography.labelMedium,
                            color = CallBlue,
                            fontWeight = FontWeight.SemiBold
                        )
                    } else {
                        Button(
                            onClick = { onCallNow(action) },
                            colors = ButtonDefaults.buttonColors(containerColor = CallBlue),
                            shape = RoundedCornerShape(20.dp),
                            contentPadding = PaddingValues(horizontal = 14.dp, vertical = 6.dp)
                        ) {
                            Icon(
                                imageVector = Icons.Default.Call,
                                contentDescription = null,
                                tint = Color.White,
                                modifier = Modifier.size(15.dp)
                            )
                            Spacer(modifier = Modifier.width(6.dp))
                            Text(
                                text = "Call Again",
                                style = MaterialTheme.typography.labelMedium,
                                fontWeight = FontWeight.Bold,
                                color = Color.White
                            )
                        }
                    }
                }
            }
        }
    }
}
