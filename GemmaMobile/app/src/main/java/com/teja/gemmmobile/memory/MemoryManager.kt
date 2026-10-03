package com.teja.gemmmobile.memory

import android.content.Context
import android.util.Log
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.withContext
import java.io.File
import java.util.UUID

private const val TAG = "MemoryManager"
private const val MEMORY_FILE = "user_memories.json"

data class MemoryItem(
    val id: String = UUID.randomUUID().toString(),
    val fact: String,
    val createdAt: Long = System.currentTimeMillis()
)

/**
 * Manages persistent long-term memory for Gemma 4.
 * Memories are saved to disk and automatically injected into Gemma's system instructions
 * so Gemma always remembers the user, preferences, and facts across conversations.
 */
class MemoryManager(private val context: Context) {
    private val gson = Gson()
    private val file: File get() = File(context.filesDir, MEMORY_FILE)

    private val _memories = MutableStateFlow<List<MemoryItem>>(emptyList())
    val memories: StateFlow<List<MemoryItem>> = _memories.asStateFlow()

    init {
        loadMemoriesSync()
    }

    private fun loadMemoriesSync() {
        try {
            if (file.exists() && file.length() > 0L) {
                val json = file.readText()
                val type = object : TypeToken<List<MemoryItem>>() {}.type
                val list: List<MemoryItem>? = gson.fromJson(json, type)
                _memories.value = list ?: emptyList()
            }
        } catch (e: Exception) {
            Log.e(TAG, "[$TAG] Error loading memories", e)
        }
    }

    suspend fun addMemory(fact: String) = withContext(Dispatchers.IO) {
        val trimmed = fact.trim()
        if (trimmed.isBlank()) return@withContext
        val updated = _memories.value + MemoryItem(fact = trimmed)
        _memories.value = updated
        saveToDisk(updated)
    }

    suspend fun removeMemory(id: String) = withContext(Dispatchers.IO) {
        val updated = _memories.value.filterNot { it.id == id }
        _memories.value = updated
        saveToDisk(updated)
    }

    suspend fun clearAll() = withContext(Dispatchers.IO) {
        _memories.value = emptyList()
        saveToDisk(emptyList())
    }

    private fun saveToDisk(list: List<MemoryItem>) {
        try {
            val json = gson.toJson(list)
            file.writeText(json)
            Log.d(TAG, "[$TAG] Saved ${list.size} memories to disk")
        } catch (e: Exception) {
            Log.e(TAG, "[$TAG] Error saving memories to disk", e)
        }
    }

    /**
     * Formats stored memories into clean bullet points for injection into Gemma's system prompt.
     */
    fun getFormattedMemoryPrompt(): String {
        val list = _memories.value
        if (list.isEmpty()) return ""
        val bullets = list.joinToString("\n") { "• ${it.fact}" }
        return """
[PERSISTENT LONG-TERM MEMORY ABOUT THE USER]
$bullets
Always remember and apply these facts when responding to the user.
""".trim()
    }
}
