package com.teja.gemmmobile.util

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.CalendarContract
import android.widget.Toast
import com.teja.gemmmobile.storage.ChatSession
import com.teja.gemmmobile.ui.MessageRole

object ExportHelper {

    fun formatSessionAsMarkdown(session: ChatSession): String {
        val sb = StringBuilder()
        sb.append("# ${session.title}\n")
        sb.append("*Exported from GemmaMobile (On-Device Gemma 4 AI)*\n\n")

        for (msg in session.messages) {
            val role = if (msg.role == MessageRole.USER) "👤 You" else "✨ Gemma"
            sb.append("### $role\n")
            if (msg.thoughtText.isNotEmpty()) {
                sb.append("> **Thinking:**\n> ")
                sb.append(msg.thoughtText.replace("\n", "\n> "))
                sb.append("\n\n")
            }
            sb.append(msg.text.trim())
            sb.append("\n\n---\n\n")
        }

        return sb.toString().trim()
    }

    fun shareSession(context: Context, session: ChatSession) {
        val text = formatSessionAsMarkdown(session)
        val sendIntent = Intent(Intent.ACTION_SEND).apply {
            type = "text/plain"
            putExtra(Intent.EXTRA_SUBJECT, session.title)
            putExtra(Intent.EXTRA_TEXT, text)
        }
        val shareIntent = Intent.createChooser(sendIntent, "Share Chat via")
        shareIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        context.startActivity(shareIntent)
    }

    fun copySession(context: Context, session: ChatSession) {
        val text = formatSessionAsMarkdown(session)
        val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        val clip = ClipData.newPlainText("Chat Export", text)
        clipboard.setPrimaryClip(clip)
        Toast.makeText(context, "Full conversation copied to clipboard", Toast.LENGTH_SHORT).show()
    }

    fun shareMessage(context: Context, text: String) {
        val sendIntent = Intent(Intent.ACTION_SEND).apply {
            type = "text/plain"
            putExtra(Intent.EXTRA_TEXT, text)
        }
        val shareIntent = Intent.createChooser(sendIntent, "Share Message")
        shareIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        context.startActivity(shareIntent)
    }

    fun addToCalendar(context: Context, title: String, description: String) {
        try {
            val intent = Intent(Intent.ACTION_INSERT).apply {
                data = CalendarContract.Events.CONTENT_URI
                putExtra(CalendarContract.Events.TITLE, title)
                putExtra(CalendarContract.Events.DESCRIPTION, description)
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            context.startActivity(intent)
        } catch (_: Exception) {
            Toast.makeText(context, "Unable to open calendar", Toast.LENGTH_SHORT).show()
        }
    }

    fun searchGoogle(context: Context, query: String) {
        try {
            val url = "https://www.google.com/search?q=${Uri.encode(query)}"
            val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url)).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            context.startActivity(intent)
        } catch (_: Exception) {
            Toast.makeText(context, "Unable to open browser", Toast.LENGTH_SHORT).show()
        }
    }
}
