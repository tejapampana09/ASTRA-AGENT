package com.teja.gemmmobile.search

import com.google.gson.JsonObject
import com.google.gson.JsonParser
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SerperClientTest {

    @Test
    fun testIsAvailable_validatesApiKeyPresence() {
        val client = SerperClient("af077176ca8f3640dedb5573509e74048fa50e2d")
        assertTrue(client.isAvailable())

        val emptyClient = SerperClient("")
        assertFalse(emptyClient.isAvailable())
    }

    @Test
    fun testParseShoppingResponse_extractsProductsPricesAndPackshots() {
        val jsonString = """
        {
          "shopping": [
            {
              "title": "Dot & Key Watermelon Cooling Sunscreen SPF 50",
              "source": "Amazon.in",
              "link": "https://www.google.com/search?ibp=oshop&prds=catalogid:11781",
              "price": "₹224",
              "rating": 4.5,
              "ratingCount": 420,
              "imageUrl": "https://img.com/dotkey.jpg",
              "delivery": "Free delivery"
            },
            {
              "title": "Deconstruct Gel Sunscreen",
              "source": "The Deconstruct",
              "link": "https://www.thedeconstruct.com/product/sunscreen",
              "price": "₹149",
              "imageUrl": "https://img.com/deconstruct.jpg"
            }
          ]
        }
        """.trimIndent()

        val rootJson = JsonParser.parseString(jsonString).asJsonObject
        val client = SerperClient("dummy-key")

        val method = SerperClient::class.java.getDeclaredMethod(
            "parseShoppingResponse",
            JsonObject::class.java,
            String::class.java,
            Int::class.javaPrimitiveType
        )
        method.isAccessible = true
        val result = method.invoke(client, rootJson, "sunscreen", 5) as SerpApiResult

        assertEquals(2, result.results.size)
        assertEquals("Dot & Key Watermelon Cooling Sunscreen SPF 50", result.results[0].title)
        assertEquals("https://www.google.com/search?ibp=oshop&prds=catalogid:11781", result.results[0].url)
        assertTrue(result.results[0].snippet.contains("₹224 on Amazon.in"))

        assertEquals("Deconstruct Gel Sunscreen", result.results[1].title)
        assertTrue(result.results[1].snippet.contains("₹149 on The Deconstruct"))

        assertEquals(2, result.images.size)
        assertEquals("https://img.com/dotkey.jpg", result.images[0].imageUrl)
        assertEquals("Amazon.in", result.images[0].sourceDomain)
    }

    @Test
    fun testParseSearchResponse_extractsKnowledgeGraphAndOrganic() {
        val jsonString = """
        {
          "answerBox": {
            "title": "Current CEO of Google",
            "answer": "Sundar Pichai",
            "link": "https://en.wikipedia.org/wiki/Sundar_Pichai"
          },
          "knowledgeGraph": {
            "title": "Sundar Pichai",
            "type": "Business executive",
            "description": "Sundar Pichai is an Indian-American business executive.",
            "descriptionUrl": "https://en.wikipedia.org/wiki/Sundar_Pichai",
            "imageUrl": "https://img.com/sundar.jpg"
          },
          "organic": [
            {
              "title": "Google Executive Profiles",
              "link": "https://abc.xyz/leaders",
              "snippet": "Profiles of executives at Alphabet and Google."
            }
          ]
        }
        """.trimIndent()

        val rootJson = JsonParser.parseString(jsonString).asJsonObject
        val client = SerperClient("dummy-key")

        val method = SerperClient::class.java.getDeclaredMethod(
            "parseSearchResponse",
            JsonObject::class.java,
            String::class.java,
            Int::class.javaPrimitiveType
        )
        method.isAccessible = true
        val result = method.invoke(client, rootJson, "ceo of google", 5) as SerpApiResult

        assertTrue(result.results.any { it.title == "Current CEO of Google" && it.snippet == "Sundar Pichai" })
        assertTrue(result.results.any { it.title == "Google Executive Profiles" })
        assertTrue(result.images.any { it.imageUrl == "https://img.com/sundar.jpg" })
    }
}
