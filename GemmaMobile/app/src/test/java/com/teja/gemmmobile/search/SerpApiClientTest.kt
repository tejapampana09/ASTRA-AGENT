package com.teja.gemmmobile.search

import com.google.gson.JsonParser
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SerpApiClientTest {

    @Test
    fun testIsAvailable_checksApiKeyPresence() {
        val clientWithKey = SerpApiClient("test-key-123")
        assertTrue(clientWithKey.isAvailable())

        val clientEmptyKey = SerpApiClient("")
        assertFalse(clientEmptyKey.isAvailable())

        val clientBlankKey = SerpApiClient("   ")
        assertFalse(clientBlankKey.isAvailable())
    }

    @Test
    fun testParseShoppingResponse_extractsProductsPricesAndThumbnails() {
        val jsonString = """
        {
          "shopping_results": [
            {
              "position": 1,
              "title": "Minimalist SPF 50 Sunscreen",
              "product_link": "https://www.google.com/search?ibp=oshop&prds=catalogid:999",
              "source": "Amazon.in",
              "price": "₹399",
              "extracted_price": 399,
              "rating": 4.6,
              "reviews": 120,
              "thumbnail": "https://img.com/minimalist.jpg",
              "delivery": "Free delivery"
            },
            {
              "position": 2,
              "title": "Aqualogica Water-Light Sunscreen",
              "link": "https://www.purplle.com/p/aqualogica",
              "source": "Purplle.com",
              "extracted_price": 499,
              "rating": 4.5,
              "reviews": 85,
              "thumbnail": "https://img.com/aqualogica.jpg"
            }
          ]
        }
        """.trimIndent()

        val rootJson = JsonParser.parseString(jsonString).asJsonObject
        val client = SerpApiClient("dummy-key")

        // Use reflection to access private parseShoppingResponse for exact unit test validation
        val method = SerpApiClient::class.java.getDeclaredMethod(
            "parseShoppingResponse",
            com.google.gson.JsonObject::class.java,
            String::class.java,
            Int::class.javaPrimitiveType
        )
        method.isAccessible = true
        val result = method.invoke(client, rootJson, "sunscreen", 5) as SerpApiResult

        assertEquals(2, result.results.size)
        assertEquals("Minimalist SPF 50 Sunscreen", result.results[0].title)
        assertEquals("https://www.google.com/search?ibp=oshop&prds=catalogid:999", result.results[0].url)
        assertTrue(result.results[0].snippet.contains("₹399 on Amazon.in"))
        assertTrue(result.results[0].snippet.contains("4.6★"))

        assertEquals("Aqualogica Water-Light Sunscreen", result.results[1].title)
        assertEquals("https://www.purplle.com/p/aqualogica", result.results[1].url)
        assertTrue(result.results[1].snippet.contains("₹499 on Purplle.com"))

        assertEquals(2, result.images.size)
        assertEquals("https://img.com/minimalist.jpg", result.images[0].imageUrl)
        assertEquals("Amazon.in", result.images[0].sourceDomain)
        assertEquals("https://img.com/aqualogica.jpg", result.images[1].imageUrl)
        assertEquals("Purplle.com", result.images[1].sourceDomain)
    }

    @Test
    fun testParseGoogleResponse_extractsOrganicAndKnowledgeGraph() {
        val jsonString = """
        {
          "answer_box": {
            "title": "Capital of Telangana",
            "answer": "Hyderabad",
            "link": "https://en.wikipedia.org/wiki/Hyderabad"
          },
          "knowledge_graph": {
            "title": "Hyderabad",
            "type": "City in India",
            "description": "Hyderabad is the capital and largest city of the Indian state of Telangana.",
            "source": {
              "link": "https://en.wikipedia.org/wiki/Hyderabad"
            }
          },
          "organic_results": [
            {
              "title": "Official Portal of Telangana Government",
              "link": "https://telangana.gov.in",
              "snippet": "Government of Telangana official website with portals and schemes.",
              "thumbnail": "https://img.com/tg_logo.png"
            }
          ]
        }
        """.trimIndent()

        val rootJson = JsonParser.parseString(jsonString).asJsonObject
        val client = SerpApiClient("dummy-key")

        val method = SerpApiClient::class.java.getDeclaredMethod(
            "parseGoogleResponse",
            com.google.gson.JsonObject::class.java,
            String::class.java,
            Int::class.javaPrimitiveType
        )
        method.isAccessible = true
        val result = method.invoke(client, rootJson, "capital of telangana", 5) as SerpApiResult

        assertTrue(result.results.any { it.title == "Capital of Telangana" && it.snippet == "Hyderabad" })
        assertTrue(result.results.any { it.title == "Official Portal of Telangana Government" })
        assertTrue(result.images.any { it.imageUrl == "https://img.com/tg_logo.png" })
    }
}
