from __future__ import annotations

import re
from pathlib import Path
from typing import List, Tuple

from app.observability.logging import logger


class SecurityPolicyViolation(Exception):
    """Raised when an operation violates ASTRA security policies."""
    pass


class SecurityPolicies:
    """Enforces safety guardrails against malicious repository content and destructive commands."""

    BLOCKED_COMMAND_PATTERNS: List[re.Pattern] = [
        re.compile(r"\brm\s+-rf\s+[/~]", re.IGNORECASE),
        re.compile(r"\bdel\s+/[sfq]\s+c:\\", re.IGNORECASE),
        re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", re.IGNORECASE),  # Fork bomb
        re.compile(r"\bmkfs\b", re.IGNORECASE),
        re.compile(r"\bdd\s+if=.*of=/dev/(sd|nvme|hd)", re.IGNORECASE),
        re.compile(r"\bshutdown\b", re.IGNORECASE),
        re.compile(r"\breboot\b", re.IGNORECASE),
        re.compile(r">\s*/dev/sda", re.IGNORECASE),
        re.compile(r"\bcurl.*\|\s*(bash|sh)", re.IGNORECASE),
        re.compile(r"\bwget.*\|\s*(bash|sh)", re.IGNORECASE),
    ]

    SUSPICIOUS_PROMPT_INJECTIONS: List[re.Pattern] = [
        re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
        re.compile(r"you\s+are\s+no\s+longer\s+an\s+agent", re.IGNORECASE),
        re.compile(r"system\s*:\s*override", re.IGNORECASE),
        re.compile(r"print\s+(the\s+)?(api[_-]?key|secret|env|password)", re.IGNORECASE),
    ]

    @classmethod
    def validate_command(cls, command: str) -> Tuple[bool, str]:
        """Validates that a terminal command does not violate safety policies."""
        cleaned = command.strip()
        for pattern in cls.BLOCKED_COMMAND_PATTERNS:
            if pattern.search(cleaned):
                msg = f"Command blocked by ASTRA security policy: {command}"
                logger.error(msg)
                return False, msg
        return True, "Command allowed"

    @classmethod
    def sanitize_untrusted_input(cls, text: str) -> str:
        """
        Sanitizes text originating from repository files (e.g. README, issues)
        to prevent prompt injection against the agent.
        """
        for pattern in cls.SUSPICIOUS_PROMPT_INJECTIONS:
            if pattern.search(text):
                logger.warning("Potential prompt injection attempt detected in repository content. Neutralizing.")
                text = pattern.sub("[REDACTED_SUSPICIOUS_INSTRUCTION]", text)
        return text
