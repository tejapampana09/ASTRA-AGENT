package com.teja.gemmmobile.storage

import android.content.Context
import android.util.Log
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import com.teja.gemmmobile.ui.ChatMessage
import com.teja.gemmmobile.ui.MessageRole
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.util.UUID

private const val TAG = "ChatStorage"
private const val SESSIONS_FILE = "chat_sessions.json"
private const val LEGACY_CHAT_FILE = "chat_history.json"

/**
 * Representation of an individual chat session.
 */
data class ChatSession(
    val id: String = UUID.randomUUID().toString(),
    val title: String = "New Chat",
    val createdAt: Long = System.currentTimeMillis(),
    val updatedAt: Long = System.currentTimeMillis(),
    val messages: List<ChatMessage> = emptyList()
)

/**
 * Local file storage for persisting multiple chat sessions across app opens and closes.
 */
class ChatStorage(private val context: Context) {
    private val gson = Gson()
    private val sessionsFile: File get() = File(context.filesDir, SESSIONS_FILE)
    private val legacyFile: File get() = File(context.filesDir, LEGACY_CHAT_FILE)

    suspend fun loadSessions(): List<ChatSession> = withContext(Dispatchers.IO) {
        try {
            if (sessionsFile.exists() && sessionsFile.length() > 0L) {
                val json = sessionsFile.readText()
                val type = object : TypeToken<List<ChatSession>>() {}.type
                val list: List<ChatSession>? = gson.fromJson(json, type)
                if (!list.isNullOrEmpty()) {
                    return@withContext list.sortedByDescending { it.updatedAt }
                }
            }

            // Migration from legacy single chat_history.json
            if (legacyFile.exists() && legacyFile.length() > 0L) {
                val legacyJson = legacyFile.readText()
                val type = object : TypeToken<List<ChatMessage>>() {}.type
                val legacyMessages: List<ChatMessage>? = gson.fromJson(legacyJson, type)
                if (!legacyMessages.isNullOrEmpty()) {
                    val firstUserMsg = legacyMessages.firstOrNull { it.role == MessageRole.USER }?.text?.trim()
                    val title = if (!firstUserMsg.isNullOrBlank()) {
                        firstUserMsg.take(35)
                    } else "Previous Chat"
                    val migratedSession = ChatSession(
                        id = UUID.randomUUID().toString(),
                        title = title,
                        messages = legacyMessages
                    )
                    saveSessionsInternal(listOf(migratedSession))
                    legacyFile.delete()
                    return@withContext listOf(migratedSession)
                }
            }
            emptyList()
        } catch (e: Exception) {
            Log.e(TAG, "[$TAG] Error loading chat sessions", e)
            emptyList()
        }
    }

    suspend fun saveSession(session: ChatSession) = withContext(Dispatchers.IO) {
        try {
            val sessions = loadSessions().toMutableList()
            val index = sessions.indexOfFirst { it.id == session.id }
            val sanitized = session.copy(
                messages = session.messages.map { it.copy(isStreaming = false, isThinking = false, isSearchingWeb = false) }
            )
            if (index != -1) {
                sessions[index] = sanitized
            } else {
                sessions.add(0, sanitized)
            }
            saveSessionsInternal(sessions.sortedByDescending { it.updatedAt })
        } catch (e: Exception) {
            Log.e(TAG, "[$TAG] Error saving chat session", e)
        }
    }

    suspend fun deleteSession(sessionId: String): List<ChatSession> = withContext(Dispatchers.IO) {
        try {
            val sessions = loadSessions().filter { it.id != sessionId }
            saveSessionsInternal(sessions)
            sessions
        } catch (e: Exception) {
            Log.e(TAG, "[$TAG] Error deleting chat session", e)
            emptyList()
        }
    }

    suspend fun renameSession(sessionId: String, newTitle: String): List<ChatSession> = withContext(Dispatchers.IO) {
        try {
            val sessions = loadSessions().map {
                if (it.id == sessionId) it.copy(title = newTitle.trim(), updatedAt = System.currentTimeMillis())
                else it
            }
            saveSessionsInternal(sessions.sortedByDescending { it.updatedAt })
            sessions.sortedByDescending { it.updatedAt }
        } catch (e: Exception) {
            Log.e(TAG, "[$TAG] Error renaming chat session", e)
            loadSessions()
        }
    }

    suspend fun clearAllSessions() = withContext(Dispatchers.IO) {
        try {
            if (sessionsFile.exists()) sessionsFile.delete()
            if (legacyFile.exists()) legacyFile.delete()
            Log.d(TAG, "[$TAG] All chat sessions cleared")
        } catch (e: Exception) {
            Log.e(TAG, "[$TAG] Error clearing all sessions", e)
        }
    }

    private fun saveSessionsInternal(sessions: List<ChatSession>) {
        val json = gson.toJson(sessions)
        sessionsFile.writeText(json)
        Log.d(TAG, "[$TAG] Persisted ${sessions.size} chat sessions to disk")
    }
}
