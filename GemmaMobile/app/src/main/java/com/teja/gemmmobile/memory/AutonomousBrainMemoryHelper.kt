package com.teja.gemmmobile.memory

import java.util.Locale

sealed class MemoryBrainAction {
    data class Add(val fact: String) : MemoryBrainAction()
    data class Forget(val keyword: String) : MemoryBrainAction()
}

/**
 * Autonomous Brain & Memory Engine for ASTRA (ChatGPT Style).
 * Automatically extracts user facts, background, and preferences from natural conversation
 * without requiring the user to explicitly say "remember this".
 * Also handles autonomous deletion when user asks to forget something.
 */
object AutonomousBrainMemoryHelper {

    /**
     * Analyzes natural conversation turns (English and Telugu) to extract lasting personal facts.
     */
    fun evaluateUserUtterance(text: String, existingMemories: List<MemoryItem>): MemoryBrainAction? {
        val trimmed = text.trim()
        if (trimmed.length < 4 || trimmed.length > 300) return null
        val lower = trimmed.lowercase(Locale.ROOT)

        // 1. Explicit Forget / Delete Commands
        val forgetPrefixes = listOf(
            "forget that ", "forget my ", "forget about ", "forget ",
            "delete memory about ", "delete memory ", "remove memory "
        )
        for (prefix in forgetPrefixes) {
            if (lower.startsWith(prefix)) {
                val target = trimmed.substring(prefix.length).trim().removeSuffix(".")
                if (target.isNotBlank()) return MemoryBrainAction.Forget(target)
            }
        }

        // 2. Explicit Remember Commands
        val rememberPrefixes = listOf(
            "remember that ", "remember my ", "remember: ", "remember ",
            "save to memory: ", "keep in mind that "
        )
        for (prefix in rememberPrefixes) {
            if (lower.startsWith(prefix)) {
                val fact = trimmed.substring(prefix.length).trim().removeSuffix(".")
                if (fact.length > 3 && !isFactAlreadyPresent(fact, existingMemories)) {
                    return MemoryBrainAction.Add(formatFact(fact))
                }
            }
        }

        // 3. Autonomous Name & Identity
        // "My name is Teja", "I am Teja", "Na peru Teja", "Nenu Teja"
        val nameRegex = Regex("""^(?:my name is|i am|call me|na peru|naa peru)\s+([A-Z][a-zA-Z\s]{1,30})""", RegexOption.IGNORE_CASE)
        val nameMatch = nameRegex.find(trimmed)
        if (nameMatch != null) {
            val name = nameMatch.groupValues[1].trim()
            val fact = "User's name is $name"
            if (!isFactAlreadyPresent(fact, existingMemories)) {
                return MemoryBrainAction.Add(fact)
            }
        }

        // 4. Autonomous Location / Residence
        // "I live in Hyderabad", "I am from Vizag", "Nenu Hyderabad lo untanu", "Maadi Vijayawada"
        val locationRegex = Regex("""^(?:i live in|i am from|i'm from|i am based in|based in|nenu)\s+([A-Za-z\s]+?)(?:\s+lo untanu|\s+lo unta|\.|\$)?$""", RegexOption.IGNORE_CASE)
        val locMatch = locationRegex.find(trimmed)
        if (locMatch != null && !lower.contains("how") && !lower.contains("why")) {
            val city = locMatch.groupValues[1].trim().replaceFirstChar { it.uppercase() }
            if (city.length in 3..35 && !city.equals("a", true) && !city.equals("the", true)) {
                val fact = "User lives in $city"
                if (!isFactAlreadyPresent(fact, existingMemories)) {
                    return MemoryBrainAction.Add(fact)
                }
            }
        }

        // 5. Autonomous Profession / Student Status
        // "I am a software engineer", "I work at Google", "I am a B.Tech student", "Nenu engineer ni"
        val roleRegex = Regex("""^(?:i am a|i am an|i'm a|i'm an|i work as a|i work as an|i work at)\s+([A-Za-z0-9\.\s]{3,40})""", RegexOption.IGNORE_CASE)
        val roleMatch = roleRegex.find(trimmed)
        if (roleMatch != null && !lower.contains("question") && !lower.contains("fan of")) {
            val role = roleMatch.groupValues[1].trim()
            val fact = "User works as or is: $role"
            if (!isFactAlreadyPresent(fact, existingMemories)) {
                return MemoryBrainAction.Add(fact)
            }
        }

        // 6. Autonomous Technical & Language Preferences
        // "I prefer Kotlin over Java", "My favorite language is Python", "Always write code in Kotlin"
        val prefRegex = Regex("""^(?:i prefer|my favorite language is|my favourite language is|always give code in|always write code in)\s+([A-Za-z0-9\+\#\s]{2,40})""", RegexOption.IGNORE_CASE)
        val prefMatch = prefRegex.find(trimmed)
        if (prefMatch != null) {
            val pref = prefMatch.groupValues[1].trim()
            val fact = "User preference: $pref"
            if (!isFactAlreadyPresent(fact, existingMemories)) {
                return MemoryBrainAction.Add(fact)
            }
        }

        // 7. Telugu Preferences & Identity
        // "Naaku Python ishtam", "Naaku dark mode ishtam"
        if (lower.contains("ishtam") || lower.contains("istam")) {
            val clean = trimmed.replace(Regex("""(?i)\s+(ishtam|istam)"""), "").trim()
            if (clean.isNotBlank() && clean.length in 4..40) {
                val fact = "User likes/prefers: $clean"
                if (!isFactAlreadyPresent(fact, existingMemories)) {
                    return MemoryBrainAction.Add(fact)
                }
            }
        }

        return null
    }

    private fun isFactAlreadyPresent(fact: String, existing: List<MemoryItem>): Boolean {
        val fLower = fact.lowercase(Locale.ROOT)
        return existing.any { item ->
            val exLower = item.fact.lowercase(Locale.ROOT)
            exLower == fLower || exLower.contains(fLower) || fLower.contains(exLower)
        }
    }

    private fun formatFact(raw: String): String {
        var clean = raw.trim()
        clean = clean.replace(Regex("""^(?:that\s+|my\s+)""", RegexOption.IGNORE_CASE), "")
        return clean.replaceFirstChar { it.uppercase() }
    }
}
