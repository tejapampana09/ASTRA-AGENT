package com.teja.gemmmobile.search

import androidx.compose.runtime.Immutable

/**
 * Data model for an image discovered via web search or extracted from verified public webpages.
 */
@Immutable
data class SearchImage(
    val title: String,
    val imageUrl: String,
    val sourceUrl: String,
    val sourceDomain: String = ""
)
