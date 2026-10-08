package com.teja.gemmmobile

import android.content.Context
import com.teja.gemmmobile.model.ModelInstallState
import com.teja.gemmmobile.model.ModelManager
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File

class ModelManagerTest {

    @get:Rule
    val tempFolder = TemporaryFolder()

    private lateinit var mockContext: DummyContext
    private lateinit var modelManager: ModelManager

    // Lightweight test context without Android runtime dependency
    class DummyContext(private val baseDir: File) : android.content.ContextWrapper(null) {
        override fun getFilesDir(): File = File(baseDir, "files").apply { mkdirs() }
        override fun getExternalFilesDir(type: String?): File = File(baseDir, "external/$type").apply { mkdirs() }
    }

    @Before
    fun setup() {
        val root = tempFolder.newFolder("app_root")
        mockContext = DummyContext(root)
        modelManager = ModelManager(mockContext)
    }

    @Test
    fun testFormatSizeCalculations() {
        assertEquals("0 B", modelManager.formatSize(0))
        assertEquals("1 KB", modelManager.formatSize(1024))
        assertEquals("1 MB", modelManager.formatSize(1024 * 1024))
        val size2_58Gb = modelManager.formatSize(2_768_240_640L)
        assertTrue(size2_58Gb.contains("2.58") && size2_58Gb.contains("GB"))
    }

    @Test
    fun testModelAvailabilityWhenMissing() = runBlocking {
        val state = modelManager.checkModelAvailability()
        assertTrue(state is ModelInstallState.NotInstalled)
    }

    @Test
    fun testModelAvailabilityWhenPresent() = runBlocking {
        val file = modelManager.defaultModelFile
        file.parentFile?.mkdirs()
        java.io.RandomAccessFile(file, "rw").use { it.setLength(2_000_000_000L) }

        val state = modelManager.checkModelAvailability()
        assertTrue(state is ModelInstallState.Installed)
        val installed = state as ModelInstallState.Installed
        assertEquals(file.absolutePath, installed.modelFile.absolutePath)
        assertEquals(2_000_000_000L, installed.sizeBytes)
    }
}
