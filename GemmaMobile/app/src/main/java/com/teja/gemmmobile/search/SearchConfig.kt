package com.teja.gemmmobile.search

/**
 * Centralized configuration constants for web search, page fetching, and image retrieval.
 * Enforces uniform safety, memory caps, and context token ceilings.
 */
object SearchConfig {
    // Network Timeouts
    const val CONNECT_TIMEOUT_MS = 3500
    const val READ_TIMEOUT_MS = 4000
    const val IMAGE_CONNECT_TIMEOUT_MS = 3000
    const val IMAGE_READ_TIMEOUT_MS = 3500
    const val PER_PAGE_TIMEOUT_MS = 3000L

    // Byte and Allocation Caps (Memory Safety)
    const val MAX_PAGE_DOWNLOAD_BYTES = 512 * 1024 // 512 KB
    const val MAX_IMAGE_DOWNLOAD_BYTES = 2 * 1024 * 1024 // 2 MB
    const val MAX_AVATAR_DOWNLOAD_BYTES = 512 * 1024 // 512 KB
    const val MAX_BITMAP_DIMENSION = 960
    const val MAX_AVATAR_DIMENSION = 200

    // Content Length & Concurrency Caps
    const val MAX_PAGE_CONTENT_CHARS = 3000
    const val MAX_REDIRECTS = 3
    const val DEFAULT_MAX_SEARCH_RESULTS = 6
    const val MAX_PAGES_TO_FETCH = 2
    const val MAX_CONCURRENT_FETCHES = 2

    // Context Window Safety (strictly bounded to fit LiteRT-LM 2048 KV-cache limit)
    const val MAX_WEB_CONTEXT_CHARS = 900
    const val MAX_WEB_OUTPUT_TOKENS = 650
    const val MAX_TOOL_ARG_STRING_CHARS = 400
    const val MAX_TOOL_STEPS = 2

    // SerpApi Integration (Google Search & Google Shopping in India)
    const val SERPAPI_API_KEY = "77a8af2e3411caef9992f78048d65849e220f0d0d5469bb91edca1993b8567de"
    const val SERPAPI_BASE_URL = "https://serpapi.com/search.json"
    const val SERPAPI_CONNECT_TIMEOUT_MS = 4500
    const val SERPAPI_READ_TIMEOUT_MS = 5500
    const val SERPAPI_COUNTRY = "in"
    const val SERPAPI_LANGUAGE = "en"
}
