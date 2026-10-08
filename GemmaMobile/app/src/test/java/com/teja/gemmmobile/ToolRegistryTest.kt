package com.teja.gemmmobile

import com.teja.gemmmobile.tools.GemmaTool
import com.teja.gemmmobile.tools.ToolRegistry
import com.teja.gemmmobile.tools.ToolResult
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class ToolRegistryTest {

    private lateinit var registry: ToolRegistry

    private val mockTool = object : GemmaTool {
        override val name: String = "test_tool"
        override val description: String = "A test tool"
        override val parametersJsonSchema: String = """{"type": "object"}"""
        override suspend fun execute(arguments: Map<String, Any?>): ToolResult {
            val echo = arguments["input"] as? String ?: "default"
            return ToolResult.success("echo: $echo")
        }
    }

    @Before
    fun setup() {
        registry = ToolRegistry()
        registry.register(mockTool)
    }

    @Test
    fun testRegisterAndRetrieve() {
        assertNotNull(registry.get("test_tool"))
        assertNull(registry.get("non_existent"))
        assertEquals(1, registry.getAll().size)
    }

    @Test
    fun testParseRawJsonToolCall() {
        val json = """{"type": "tool_call", "name": "test_tool", "arguments": {"input": "hello world"}}"""
        val parsed = registry.parseToolCall(json)
        assertNotNull(parsed)
        assertEquals("test_tool", parsed?.name)
        assertEquals("hello world", parsed?.arguments?.get("input"))
    }

    @Test
    fun testParseMarkdownWrappedToolCall() {
        val markdown = """
            I will run the tool now:
            ```json
            {
               "name": "test_tool",
               "arguments": {
                   "input": "from_markdown"
               }
            }
            ```
        """.trimIndent()
        val parsed = registry.parseToolCall(markdown)
        assertNotNull(parsed)
        assertEquals("test_tool", parsed?.name)
        assertEquals("from_markdown", parsed?.arguments?.get("input"))
    }

    @Test
    fun testParseIgnoresUnregisteredTool() {
        val json = """{"name": "unknown_tool", "arguments": {}}"""
        val parsed = registry.parseToolCall(json)
        assertNull(parsed)
    }

    @Test
    fun testExecuteTool() = runBlocking {
        val result = registry.execute("test_tool", mapOf("input" to "Antigravity"))
        assertTrue(result.success)
        assertEquals("echo: Antigravity", result.content)
    }

    @Test
    fun testExecuteUnknownTool() = runBlocking {
        val result = registry.execute("unknown", emptyMap())
        assertTrue(!result.success)
        assertTrue(result.error?.contains("Unknown tool") == true)
    }
}
