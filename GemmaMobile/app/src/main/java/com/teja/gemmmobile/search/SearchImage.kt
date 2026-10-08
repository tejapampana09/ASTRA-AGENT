package com.teja.gemmmobile.search

/**
 * Data model for an image discovered via web search or extracted from verified public webpages.
 */
data class SearchImage(
    val title: String,
    val imageUrl: String,
    val sourceUrl: String,
    val sourceDomain: String = ""
)
