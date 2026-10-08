package com.teja.gemmmobile.search

/**
 * Centralized configuration constants for web search, page fetching, and image retrieval.
 * Eliminates scattered magic numbers and enforces uniform safety and performance ceilings.
 */
object SearchConfig {
    // Network Timeouts
    const val CONNECT_TIMEOUT_MS = 3500
    const val READ_TIMEOUT_MS = 4500
    const val IMAGE_CONNECT_TIMEOUT_MS = 3000
    const val IMAGE_READ_TIMEOUT_MS = 3500
    const val PER_PAGE_TIMEOUT_MS = 4500L

    // Byte and Allocation Caps (Memory Safety)
    const val MAX_PAGE_DOWNLOAD_BYTES = 768 * 1024 // 768 KB
    const val MAX_IMAGE_DOWNLOAD_BYTES = 2 * 1024 * 1024 // 2 MB
    const val MAX_AVATAR_DOWNLOAD_BYTES = 512 * 1024 // 512 KB
    const val MAX_BITMAP_DIMENSION = 960
    const val MAX_AVATAR_DIMENSION = 200

    // Content Length & Concurrency Caps
    const val MAX_PAGE_CONTENT_CHARS = 5000
    const val MAX_REDIRECTS = 4
    const val DEFAULT_MAX_SEARCH_RESULTS = 5
    const val MAX_PAGES_TO_FETCH = 4
    const val MAX_CONCURRENT_FETCHES = 3

    // Context Window Safety (aligned with ContextManager 1100 token KV-cache budget)
    const val MAX_WEB_CONTEXT_CHARS = 1400
    const val MAX_TOOL_ARG_STRING_CHARS = 500
    const val MAX_TOOL_STEPS = 3
}
