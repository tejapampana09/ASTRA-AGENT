package com.teja.gemmmobile

import com.teja.gemmmobile.assistant.CallAction
import com.teja.gemmmobile.assistant.CallStatus
import com.teja.gemmmobile.assistant.WhatsAppAction
import com.teja.gemmmobile.assistant.WhatsAppStatus
import com.teja.gemmmobile.tools.CallTool
import com.teja.gemmmobile.tools.WhatsAppTool
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File

class ToolConfirmationTest {

    @get:Rule
    val tempFolder = TemporaryFolder()

    class TestContext(private val baseDir: File) : android.content.ContextWrapper(null) {
        override fun getFilesDir(): File = File(baseDir, "files").apply { mkdirs() }
        override fun getSharedPreferences(name: String?, mode: Int): android.content.SharedPreferences {
            return object : android.content.SharedPreferences {
                override fun getAll(): MutableMap<String, *> = mutableMapOf<String, Any>()
                override fun getString(key: String?, defValue: String?): String? = defValue
                override fun getStringSet(key: String?, defValues: MutableSet<String>?): MutableSet<String>? = defValues
                override fun getInt(key: String?, defValue: Int): Int = defValue
                override fun getLong(key: String?, defValue: Long): Long = defValue
                override fun getFloat(key: String?, defValue: Float): Float = defValue
                override fun getBoolean(key: String?, defValue: Boolean): Boolean = defValue
                override fun contains(key: String?): Boolean = false
                override fun edit(): android.content.SharedPreferences.Editor = object : android.content.SharedPreferences.Editor {
                    override fun putString(key: String?, value: String?) = this
                    override fun putStringSet(key: String?, values: MutableSet<String>?) = this
                    override fun putInt(key: String?, value: Int) = this
                    override fun putLong(key: String?, value: Long) = this
                    override fun putFloat(key: String?, value: Float) = this
                    override fun putBoolean(key: String?, value: Boolean) = this
                    override fun remove(key: String?) = this
                    override fun clear() = this
                    override fun commit(): Boolean = true
                    override fun apply() {}
                }
                override fun registerOnSharedPreferenceChangeListener(listener: android.content.SharedPreferences.OnSharedPreferenceChangeListener?) {}
                override fun unregisterOnSharedPreferenceChangeListener(listener: android.content.SharedPreferences.OnSharedPreferenceChangeListener?) {}
            }
        }
    }

    @Test
    fun testCallToolWithDirectNumberAwaitsConfirmation() = runBlocking {
        val root = tempFolder.newFolder("call_test")
        val ctx = TestContext(root)
        val tool = CallTool(ctx)

        val result = tool.execute(mapOf("contact_name" to "9542696946"))
        assertTrue(result.success)
        val action = result.data as? CallAction
        assertNotNull(action)
        assertEquals(CallStatus.AWAITING_CONFIRMATION, action?.status)
        assertTrue(result.content.contains("Awaiting user confirmation"))
    }

    @Test
    fun testWhatsAppToolWithoutMatchReturnsNoContactStatus() = runBlocking {
        val root = tempFolder.newFolder("whatsapp_test")
        val ctx = TestContext(root)
        val tool = WhatsAppTool(ctx)

        val result = tool.execute(mapOf("contact_name" to "UnknownPerson", "message" to "Hi"))
        assertTrue(result.success)
        val action = result.data as? WhatsAppAction
        assertNotNull(action)
        assertEquals(WhatsAppStatus.NO_CONTACT_FOUND, action?.status)
    }
}
