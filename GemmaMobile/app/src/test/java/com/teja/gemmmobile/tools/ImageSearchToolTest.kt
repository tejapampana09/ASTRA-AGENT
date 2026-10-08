package com.teja.gemmmobile.tools

import com.teja.gemmmobile.search.SearchImage
import com.teja.gemmmobile.search.SearchManager
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ImageSearchToolTest {

    @Test
    fun testImageSearchTool_emptyQueryRejected() = runBlocking {
        val tool = ImageSearchTool()
        val res1 = tool.execute(emptyMap())
        assertFalse(res1.success)
        assertTrue(res1.error?.contains("'query' is required") == true)

        val res2 = tool.execute(mapOf("query" to "   "))
        assertFalse(res2.success)
        assertTrue(res2.error?.contains("cannot be blank") == true)
    }

    @Test
    fun testImageSearchTool_oversizedQueryRejected() = runBlocking {
        val tool = ImageSearchTool()
        val longQuery = "X".repeat(600)
        val res = tool.execute(mapOf("query" to longQuery))
        assertFalse(res.success)
        assertTrue(res.error?.contains("exceeds maximum length limit") == true)
    }

    @Test
    fun testImageSearchTool_validExecutionWithMockManager() = runBlocking {
        val mockManager = object : SearchManager() {
            override suspend fun searchImages(
                query: String,
                enrichedPages: List<com.teja.gemmmobile.search.EnrichedSearchResult>,
                maxImages: Int
            ): List<SearchImage> {
                return listOf(
                    SearchImage(
                        title = "VAE Architecture",
                        imageUrl = "https://example.com/vae.png",
                        sourceUrl = "https://example.com/article",
                        sourceDomain = "example.com"
                    )
                )
            }
        }

        val tool = ImageSearchTool(searchManager = mockManager)
        val res = tool.execute(mapOf("query" to "VAE architecture", "max_results" to 3))

        assertTrue(res.success)
        assertTrue(res.content.contains("FOUND 1 IMAGES FOR: \"VAE architecture\""))
        assertTrue(res.content.contains("https://example.com/vae.png"))

        val dataList = res.data as? List<*>
        assertTrue(dataList != null && dataList.size == 1)
        val item = dataList?.first() as? SearchImage
        assertEquals("VAE Architecture", item?.title)
        assertEquals("https://example.com/vae.png", item?.imageUrl)
    }

    @Test
    fun testImageSearchTool_noResultsFound() = runBlocking {
        val mockManager = object : SearchManager() {
            override suspend fun searchImages(
                query: String,
                enrichedPages: List<com.teja.gemmmobile.search.EnrichedSearchResult>,
                maxImages: Int
            ): List<SearchImage> = emptyList()
        }

        val tool = ImageSearchTool(searchManager = mockManager)
        val res = tool.execute(mapOf("query" to "some nonexistent thing"))

        assertTrue(res.success)
        assertTrue(res.content.contains("No images found"))
        val dataList = res.data as? List<*>
        assertTrue(dataList?.isEmpty() == true)
    }
}
