package com.teja.gemmmobile.assistant

import android.app.Activity
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.imePadding
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.core.view.WindowCompat
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

class AssistantActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // Allow content to draw behind system bars, but let IME push content up
        WindowCompat.setDecorFitsSystemWindows(window, false)

        setContent {

            var pendingAction by remember { mutableStateOf<WhatsAppAction?>(null) }

            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .imePadding(),
                contentAlignment = Alignment.BottomCenter
            ) {
                GeminiAssistantSheet(
                    onDismiss = {
                        finish()
                        overridePendingTransition(0, android.R.anim.fade_out)
                    },
                    onSubmitPrompt = { prompt ->
                        // If user enters regular prompt, we can process or launch chat
                        Toast.makeText(this@AssistantActivity, prompt, Toast.LENGTH_SHORT).show()
                    },
                    onCallContact = { contactQuery ->
                        val matches = ContactHelper.searchContact(this@AssistantActivity, contactQuery)
                        if (matches.isNotEmpty()) {
                            val best = matches.first()
                            ContactMemoryManager.rememberContact(
                                context = this@AssistantActivity,
                                queryKey = contactQuery,
                                fullName = best.name,
                                phoneNumber = best.phoneNumber,
                                formattedNumber = best.formattedNumber
                            )
                            CallActionHandler.makeCall(this@AssistantActivity, best.phoneNumber)
                            lifecycleScope.launch {
                                delay(300)
                                finish()
                                overridePendingTransition(0, android.R.anim.fade_out)
                            }
                        } else {
                            Toast.makeText(
                                this@AssistantActivity,
                                "Couldn't find \"$contactQuery\" in contacts",
                                Toast.LENGTH_LONG
                            ).show()
                        }
                    },
                    onWhatsAppSend = { recipient, message ->
                        val matches = ContactHelper.searchContact(this@AssistantActivity, recipient)
                        if (matches.isNotEmpty()) {
                            val best = matches.first()
                            val composed = WhatsAppActionHandler.resolveMessageBody(best.name, message)
                            pendingAction = WhatsAppAction(
                                recipientName = best.name,
                                messageText = composed,
                                rawIntent = message,
                                matchedNumber = best.phoneNumber,
                                candidateContacts = matches,
                                status = WhatsAppStatus.AWAITING_CONFIRMATION
                            )
                        } else {
                            Toast.makeText(
                                this@AssistantActivity,
                                "Couldn't find \"$recipient\" in contacts",
                                Toast.LENGTH_LONG
                            ).show()
                        }
                    },
                    pendingWhatsAppAction = pendingAction,
                    onConfirmWhatsAppSend = { action ->
                        val number = action.matchedNumber ?: return@GeminiAssistantSheet
                        // Remember contact permanently
                        ContactMemoryManager.rememberContact(
                            context = this@AssistantActivity,
                            queryKey = action.recipientName,
                            fullName = action.recipientName,
                            phoneNumber = number,
                            formattedNumber = number
                        )

                        // Send directly via accessibility
                        WhatsAppActionHandler.sendWhatsAppDirect(
                            context = this@AssistantActivity,
                            phoneNumber = number,
                            message = action.messageText,
                            autoSend = true
                        )

                        Toast.makeText(
                            this@AssistantActivity,
                            "Sent WhatsApp message to ${action.recipientName}",
                            Toast.LENGTH_SHORT
                        ).show()

                        lifecycleScope.launch {
                            delay(400)
                            finish()
                            overridePendingTransition(0, android.R.anim.fade_out)
                        }
                    },
                    onCancelWhatsAppAction = {
                        pendingAction = null
                    },
                    onSelectWhatsAppCandidate = { candidate, action ->
                        val raw = if (action.rawIntent.isNotBlank()) action.rawIntent else action.messageText
                        val reComposed = WhatsAppActionHandler.resolveMessageBody(candidate.name, raw)
                        pendingAction = action.copy(
                            recipientName = candidate.name,
                            matchedNumber = candidate.phoneNumber,
                            messageText = reComposed
                        )
                    }
                )
            }
        }
    }

    override fun finish() {
        super.finish()
        overridePendingTransition(0, android.R.anim.fade_out)
    }
}
