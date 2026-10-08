package com.teja.gemmmobile.tools

import android.util.Log
import com.google.gson.Gson
import com.google.gson.JsonElement
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import java.util.concurrent.ConcurrentHashMap

private const val TAG = "ToolRegistry"

/**
 * Central registry and dispatcher for all on-device tools.
 * Manages tool declarations, model-facing documentation, invocation parsing,
 * and safe execution.
 */
class ToolRegistry {

    private val tools = ConcurrentHashMap<String, GemmaTool>()
    private val gson = Gson()

    fun register(tool: GemmaTool) {
        tools[tool.name] = tool
        Log.d(TAG, "[$TAG] Registered tool: ${tool.name}")
    }

    fun get(name: String): GemmaTool? = tools[name]

    fun getAll(): List<GemmaTool> = tools.values.toList()

    /**
     * Generates standard system prompt documentation for all registered tools
     * instructing the model on available functions and expected calling format.
     */
    fun getToolsDocumentation(): String {
        if (tools.isEmpty()) return ""

        val sb = StringBuilder()
        sb.appendLine("## Available Tools")
        sb.appendLine("Call a tool ONLY if needed by outputting single JSON: {\"name\": \"tool_name\", \"arguments\": {\"arg\": \"val\"}}")
        tools.values.forEach { tool ->
            sb.appendLine("- `${tool.name}`: ${tool.description}")
        }
        sb.appendLine("Otherwise, answer directly.")
        return sb.toString().trim()
    }

    /**
     * Executes a tool by name with the given arguments safely catching all exceptions.
     */
    suspend fun execute(name: String, arguments: Map<String, Any?>): ToolResult {
        val tool = tools[name] ?: return ToolResult.failure("Unknown tool: '$name'")
        return try {
            Log.d(TAG, "[$TAG] Executing tool: '$name' with args: $arguments")
            tool.execute(arguments)
        } catch (t: Throwable) {
            Log.e(TAG, "[$TAG] Tool '$name' execution failed", t)
            ToolResult.failure("Error executing $name: ${t.localizedMessage ?: t.message ?: "Unknown error"}")
        }
    }

    /**
     * Parses a model generation output to determine if a structured tool call was requested.
     * Supports raw JSON, markdown-wrapped JSON (```json ... ```), and variant keys.
     */
    fun parseToolCall(rawText: String): ToolCallRequest? {
        if (rawText.isBlank()) return null

        val trimmed = rawText.trim()

        // If the model produced a substantial textual explanation (> 200 chars) and does not begin
        // directly with a tool block, treat it as a direct answer and do not intercept as a tool call.
        if (trimmed.length > 200 && !trimmed.startsWith("{") && !trimmed.startsWith("```json")) {
            return null
        }

        // 1. Try parsing directly or from markdown blocks
        val jsonCandidates = extractJsonCandidates(trimmed)

        for (candidate in jsonCandidates) {
            try {
                val element = JsonParser.parseString(candidate)
                if (!element.isJsonObject) continue

                val obj = element.asJsonObject

                // Support various format keys:
                // Pattern A: {"type": "tool_call", "name": "...", "arguments": {...}}
                // Pattern B: {"name": "...", "arguments": {...}}
                // Pattern C: {"tool": "...", "parameters": {...}}
                // Pattern D: {"tool_call": {"name": "...", "arguments": {...}}}
                val targetObj = if (obj.has("tool_call") && obj.get("tool_call").isJsonObject) {
                    obj.getAsJsonObject("tool_call")
                } else {
                    obj
                }

                val toolName = when {
                    targetObj.has("name") -> targetObj.get("name").asString
                    targetObj.has("tool") -> targetObj.get("tool").asString
                    targetObj.has("function") -> targetObj.get("function").asString
                    else -> null
                } ?: continue

                // Check if this tool is actually registered
                if (!tools.containsKey(toolName)) continue

                val args = mutableMapOf<String, Any?>()
                val argsElement = when {
                    targetObj.has("arguments") -> targetObj.get("arguments")
                    targetObj.has("parameters") -> targetObj.get("parameters")
                    targetObj.has("args") -> targetObj.get("args")
                    else -> null
                }

                if (argsElement != null && argsElement.isJsonObject) {
                    val argsObj = argsElement.asJsonObject
                    for ((key, value) in argsObj.entrySet()) {
                        args[key] = jsonElementToAny(value)
                    }
                }

                return ToolCallRequest(name = toolName, arguments = args)
            } catch (_: Exception) {
                // Not valid JSON, try next candidate
            }
        }

        return null
    }

    private fun extractJsonCandidates(text: String): List<String> {
        val candidates = mutableListOf<String>()

        // 1. Check for markdown code fences: ```json ... ``` or ``` ... ```
        val fenceRegex = Regex("""```(?:json)?\s*(\{[\s\S]*?\})\s*```""", RegexOption.IGNORE_CASE)
        val matches = fenceRegex.findAll(text)
        for (match in matches) {
            val inner = match.groupValues[1].trim()
            if (inner.startsWith("{") && inner.endsWith("}")) {
                candidates.add(inner)
            }
        }

        // 2. Whole text if it starts and ends with braces
        val trimmed = text.trim()
        if (trimmed.startsWith("{") && trimmed.endsWith("}")) {
            candidates.add(trimmed)
        }

        return candidates
    }

    private fun jsonElementToAny(element: JsonElement): Any? {
        return when {
            element.isJsonNull -> null
            element.isJsonPrimitive -> {
                val prim = element.asJsonPrimitive
                when {
                    prim.isBoolean -> prim.asBoolean
                    prim.isNumber -> prim.asNumber
                    prim.isString -> prim.asString
                    else -> prim.asString
                }
            }
            element.isJsonArray -> {
                element.asJsonArray.map { jsonElementToAny(it) }
            }
            element.isJsonObject -> {
                val map = mutableMapOf<String, Any?>()
                for ((k, v) in element.asJsonObject.entrySet()) {
                    map[k] = jsonElementToAny(v)
                }
                map
            }
            else -> element.toString()
        }
    }
}
