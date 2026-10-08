package com.teja.gemmmobile

import com.teja.gemmmobile.storage.StorageManagerHelper
import com.teja.gemmmobile.ui.ChatMessage
import com.teja.gemmmobile.ui.ChatSession
import com.teja.gemmmobile.ui.MessageRole
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File

class StorageManagerHelperTest {

    @get:Rule
    val tempFolder = TemporaryFolder()

    @Test
    fun testFormatBytes() {
        assertEquals("0 B", StorageManagerHelper.formatBytes(0L))
        assertEquals("500 B", StorageManagerHelper.formatBytes(500L))
        assertEquals("100 KB", StorageManagerHelper.formatBytes(102400L))
        assertEquals("2.5 MB", StorageManagerHelper.formatBytes((2.5 * 1024 * 1024).toLong()))
        assertEquals("2.58 GB", StorageManagerHelper.formatBytes(2_770_257_100L))
    }

    @Test
    fun testDeleteSessionImages() = runBlocking {
        val testFile = tempFolder.newFile("sample_image.jpg")
        testFile.writeText("test image data")
        assertTrue(testFile.exists())

        val msg = ChatMessage(
            id = "msg_1",
            role = MessageRole.USER,
            text = "photo query",
            imagePath = testFile.absolutePath,
            isImageAnalysis = true
        )

        StorageManagerHelper.deleteSessionImages(listOf(msg))
        assertFalse(testFile.exists())
    }
}
