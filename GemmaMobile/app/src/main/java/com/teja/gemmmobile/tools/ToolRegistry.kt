package com.teja.gemmmobile.tools

import android.util.Log
import com.google.gson.Gson
import com.google.gson.JsonElement
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import com.teja.gemmmobile.search.SearchConfig
import java.util.concurrent.ConcurrentHashMap

private const val TAG = "ToolRegistry"

/**
 * Result of validating tool arguments against its declared schema.
 */
data class ArgumentValidationResult(
    val isValid: Boolean,
    val errorMessage: String? = null
)

/**
 * Central registry, schema validator, and invocation dispatcher for all on-device tools.
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
     * Generates comprehensive system prompt documentation for all registered tools
     * clearly contrasting web_search vs image_search and direct conversation.
     */
    fun getToolsDocumentation(): String {
        if (tools.isEmpty()) return ""

        val sb = StringBuilder()
        sb.appendLine("## Available Tools & Functions")
        sb.appendLine("When you need live facts, visual diagrams, or to read documents, output ONLY a JSON object:")
        sb.appendLine("```json")
        sb.appendLine("{\"name\": \"<tool_name>\", \"arguments\": {<parameters>}}")
        sb.appendLine("```")
        sb.appendLine()
        sb.appendLine("### Decision Guidelines:")
        sb.appendLine("- Call `web_search` when the user asks for news, real-time facts, articles, website info, or text evidence.")
        sb.appendLine("- Call `image_search` when the user specifically asks to see, find, or show images, diagrams (e.g. architecture diagrams, pinouts), photos, or charts.")
        sb.appendLine("- If no tool is needed (e.g. general reasoning, coding, chit-chat), DO NOT call any tool; answer directly and conversationally.")
        sb.appendLine()
        sb.appendLine("### Tool Schemas:")
        tools.values.forEach { tool ->
            sb.appendLine("- **`${tool.name}`**: ${tool.description}")
            sb.appendLine("  Schema: `${tool.parametersJsonSchema.replace("\n", " ").replace(Regex("\\s+"), " ")}`")
        }
        return sb.toString().trim()
    }

    /**
     * Validates arguments against required schema rules before executing the tool.
     */
    fun validateArguments(tool: GemmaTool, arguments: Map<String, Any?>): ArgumentValidationResult {
        return try {
            val schemaElement = JsonParser.parseString(tool.parametersJsonSchema)
            if (!schemaElement.isJsonObject) return ArgumentValidationResult(true)

            val schemaObj = schemaElement.asJsonObject
            val requiredProps = schemaObj.getAsJsonArray("required")

            if (requiredProps != null) {
                for (elem in requiredProps) {
                    val reqField = elem.asString
                    val value = arguments[reqField]
                    if (value == null || (value is String && value.isBlank())) {
                        return ArgumentValidationResult(
                            isValid = false,
                            errorMessage = "Missing required argument '$reqField'"
                        )
                    }
                }
            }

            // String size limits check
            for ((key, value) in arguments) {
                if (value is String && value.length > SearchConfig.MAX_TOOL_ARG_STRING_CHARS) {
                    return ArgumentValidationResult(
                        isValid = false,
                        errorMessage = "Argument '$key' exceeds length limit of ${SearchConfig.MAX_TOOL_ARG_STRING_CHARS} characters"
                    )
                }
            }

            ArgumentValidationResult(isValid = true)
        } catch (e: Exception) {
            // Permissive fallback if schema parsing fails
            ArgumentValidationResult(isValid = true)
        }
    }

    /**
     * Executes a tool by name with arguments, enforcing validation and catching all errors.
     */
    suspend fun execute(name: String, arguments: Map<String, Any?>): ToolResult {
        val tool = tools[name] ?: return ToolResult.failure("Unknown tool: '$name'")

        // Enforce argument validation
        val validation = validateArguments(tool, arguments)
        if (!validation.isValid) {
            val errorMsg = validation.errorMessage ?: "Invalid arguments"
            Log.w(TAG, "[$TAG] Tool '$name' rejected invalid arguments: $errorMsg")
            return ToolResult.failure(errorMsg)
        }

        return try {
            Log.d(TAG, "[$TAG] Executing tool: '$name' with args: $arguments")
            tool.execute(arguments)
        } catch (t: Throwable) {
            Log.e(TAG, "[$TAG] Tool '$name' execution failed", t)
            ToolResult.failure("Error executing $name: ${t.localizedMessage ?: t.message ?: "Unknown error"}")
        }
    }

    /**
     * Robust balanced-brace JSON extractor that parses tool calls even when surrounded by text.
     * Example: "I should search the web.\n{"name":"web_search","arguments":{"query":"latest AI news"}}"
     */
    fun parseToolCall(rawText: String): ToolCallRequest? {
        if (rawText.isBlank()) return null

        val candidates = extractBalancedJsonCandidates(rawText)

        for (candidate in candidates) {
            try {
                val element = JsonParser.parseString(candidate)
                if (!element.isJsonObject) continue

                val obj = element.asJsonObject

                // Support pattern variations:
                // 1. {"name": "...", "arguments": {...}}
                // 2. {"tool": "...", "arguments": {...}}
                // 3. {"type": "tool_call", "name": "...", "arguments": {...}}
                // 4. {"tool_call": {"name": "...", "arguments": {...}}}
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

                // Tool must be registered in this registry
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
                // Not a valid JSON object candidate, try next
            }
        }

        return null
    }

    /**
     * Extracts all balanced { ... } substrings from text, ignoring braces inside string quotes.
     */
    fun extractBalancedJsonCandidates(text: String): List<String> {
        val candidates = mutableListOf<String>()

        // Check for markdown code fences first (```json ... ```)
        val fenceRegex = Regex("""```(?:json)?\s*(\{[\s\S]*?\})\s*```""", RegexOption.IGNORE_CASE)
        for (match in fenceRegex.findAll(text)) {
            candidates.add(match.groupValues[1].trim())
        }

        // Balanced brace scan
        var depth = 0
        var startIndex = -1
        var inString = false
        var isEscaped = false

        for (i in text.indices) {
            val c = text[i]

            if (inString) {
                if (isEscaped) {
                    isEscaped = false
                } else if (c == '\\') {
                    isEscaped = true
                } else if (c == '"') {
                    inString = false
                }
                continue
            }

            if (c == '"') {
                inString = true
                continue
            }

            if (c == '{') {
                if (depth == 0) {
                    startIndex = i
                }
                depth++
            } else if (c == '}') {
                if (depth > 0) {
                    depth--
                    if (depth == 0 && startIndex != -1) {
                        val candidate = text.substring(startIndex, i + 1).trim()
                        if (candidate.length <= 4096 && !candidates.contains(candidate)) {
                            candidates.add(candidate)
                        }
                        startIndex = -1
                    }
                }
            }
        }

        return candidates
    }

    /**
     * Helper to detect duplicate calls or loops in a sequence of tool calls.
     */
    fun isDuplicateOrLoop(
        history: List<ToolCallRequest>,
        candidate: ToolCallRequest
    ): Boolean {
        if (history.isEmpty()) return false

        // 1. Immediate duplicate check: exactly same tool and same arguments as previous
        val last = history.last()
        if (last.name == candidate.name && last.arguments == candidate.arguments) {
            return true
        }

        // 2. Ping-pong loop check: A -> B -> A -> B
        if (history.size >= 3) {
            val prev2 = history[history.size - 2]
            val prev3 = history[history.size - 3]
            if (candidate.name == prev2.name && candidate.arguments == prev2.arguments &&
                last.name == prev3.name && last.arguments == prev3.arguments
            ) {
                return true
            }
        }

        // 3. Repeated occurrences: same tool + args already called twice in cycle
        val count = history.count { it.name == candidate.name && it.arguments == candidate.arguments }
        return count >= 1
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
