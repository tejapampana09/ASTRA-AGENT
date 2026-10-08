package com.teja.gemmmobile.search

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ImageDownloadLimitsTest {

    @Test
    fun testSearchConfig_constantsAreStrictAndBounded() {
        // Assert max image download size is bounded to 2MB to protect mobile heap
        assertEquals(2 * 1024 * 1024, SearchConfig.MAX_IMAGE_DOWNLOAD_BYTES)
        // Assert max avatar download size is bounded to 512KB
        assertEquals(512 * 1024, SearchConfig.MAX_AVATAR_DOWNLOAD_BYTES)
        // Assert max bitmap dimension
        assertEquals(960, SearchConfig.MAX_BITMAP_DIMENSION)
        // Assert network timeouts are strict
        assertTrue(SearchConfig.CONNECT_TIMEOUT_MS in 3000..5000)
        assertTrue(SearchConfig.READ_TIMEOUT_MS in 3000..5000)
        assertTrue(SearchConfig.PER_PAGE_TIMEOUT_MS in 3000..5000)
    }

    @Test
    fun testProfileAvatarLoader_emptyAndInvalidUrlsReturnNull() {
        assertNull(ProfileAvatarLoader.getCached(""))
        assertNull(ProfileAvatarLoader.getCachedImage(""))
        assertNull(ProfileAvatarLoader.downloadBitmap(""))
        assertNull(ProfileAvatarLoader.downloadBitmap("   "))
    }
}
