from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from app.observability.logging import logger


class SecurityPolicyViolation(Exception):
    """Raised when an operation violates ASTRA security policies."""
    pass


class SecurityPolicies:
    """
    Production-Grade Security Policies & Attack Surface Hardening (P4.8).
    
    Protects against:
    - Destructive filesystem commands (rm -rf /, fork bombs, disk overwrites)
    - Arbitrary curl/wget remote script execution (curl | bash)
    - Cloud & Host Metadata service access (169.254.169.254, metadata.google.internal)
    - Sensitive host secrets & credential theft (/etc/shadow, ~/.ssh, ~/.aws)
    - Reverse shell creation & network exfiltration
    - Secrets leakage (API keys, tokens, .env contents) into logs, PRs, and events
    - Indirect prompt injection attacks from untrusted repository content
    """

    # 1. Strictly Prohibited Command Patterns
    BLOCKED_COMMAND_PATTERNS: List[re.Pattern] = [
        # Destructive deletions
        re.compile(r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*|-[a-zA-Z]*f[a-zA-Z]*r[a-zA-Z]*)\s+[/~]", re.IGNORECASE),
        re.compile(r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*|-[a-zA-Z]*f[a-zA-Z]*r[a-zA-Z]*)\s+/\*", re.IGNORECASE),
        re.compile(r"\bdel\s+/[sfq]\s+c:\\", re.IGNORECASE),
        re.compile(r"\brmdir\s+/[sq]\s+c:\\", re.IGNORECASE),
        # Fork bombs
        re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", re.IGNORECASE),
        # Filesystem creation / raw disk writes
        re.compile(r"\bmkfs\b", re.IGNORECASE),
        re.compile(r"\bdd\s+if=.*of=/dev/(sd|nvme|hd|zero|null)", re.IGNORECASE),
        re.compile(r">\s*/dev/sd[a-z]", re.IGNORECASE),
        re.compile(r">\s*/dev/nvme", re.IGNORECASE),
        # System shutdown / reboot
        re.compile(r"\b(shutdown|reboot|init\s+0|halt|poweroff)\b", re.IGNORECASE),
        # Arbitrary remote pipe execution
        re.compile(r"\bcurl\s+.*\|\s*(bash|sh|python|perl|zsh)\b", re.IGNORECASE),
        re.compile(r"\bwget\s+.*\|\s*(bash|sh|python|perl|zsh)\b", re.IGNORECASE),
        # Cloud metadata IP & hostname SSRF / exfiltration
        re.compile(r"169\.254\.169\.254", re.IGNORECASE),
        re.compile(r"169\.254\.170\.2", re.IGNORECASE),
        re.compile(r"metadata\.google\.internal", re.IGNORECASE),
        re.compile(r"fd00:ec2::254", re.IGNORECASE),
        re.compile(r"http://169\.254\.", re.IGNORECASE),
        # Sensitive host file / key exfiltration
        re.compile(r"/etc/(shadow|passwd|sudoers)", re.IGNORECASE),
        re.compile(r"~/\.(ssh|aws|kube)/", re.IGNORECASE),
        re.compile(r"\.ssh/(id_rsa|id_ed25519|known_hosts)", re.IGNORECASE),
        # Reverse shells
        re.compile(r"\bnc\s+.*-e\s+(/bin/sh|/bin/bash|cmd\.exe|powershell)", re.IGNORECASE),
        re.compile(r"bash\s+-i\s+>&?\s*/dev/tcp/", re.IGNORECASE),
        re.compile(r"/dev/tcp/\d+\.\d+\.\d+\.\d+/\d+", re.IGNORECASE),
        re.compile(r"pty\.spawn\(", re.IGNORECASE),
    ]

    # 2. Known Secrets Patterns
    SECRETS_PATTERNS: List[re.Pattern] = [
        re.compile(r"ghp_[a-zA-Z0-9]{20,}"),                             # GitHub PAT Classic
        re.compile(r"github_pat_[a-zA-Z0-9_]{20,}"),                     # GitHub Fine-Grained PAT
        re.compile(r"sk-[a-zA-Z0-9_-]{20,}"),                            # OpenAI / Generic Secret Key
        re.compile(r"sk-ant-[a-zA-Z0-9_-]{20,}"),                        # Anthropic API Key
        re.compile(r"AKIA[0-9A-Z]{16}"),                                 # AWS Access Key ID
        re.compile(r"bearer\s+[a-zA-Z0-9_\-\.]{24,}", re.IGNORECASE),   # Bearer JWT / Access Token
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),  # Private Key Blocks
        re.compile(r"(?i)(?:password|secret|api[_-]?key|access[_-]?token)\s*[:=]\s*['\"]([^'\"\s]{8,})['\"]"),  # Key-Value Secrets
    ]

    # 3. Prompt Injection Signatures
    PROMPT_INJECTION_PATTERNS: List[re.Pattern] = [
        re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+(instructions|directives|rules)", re.IGNORECASE),
        re.compile(r"you\s+are\s+no\s+longer\s+an\s+agent", re.IGNORECASE),
        re.compile(r"you\s+are\s+now\s+(an\s+unfiltered|in\s+developer\s+mode|dan)\b", re.IGNORECASE),
        re.compile(r"system[\s_:]+override\b", re.IGNORECASE),
        re.compile(r"disregard\s+(all\s+)?(safety|ethical)\s+guidelines", re.IGNORECASE),
        re.compile(r"(exfiltrate|leak|print|send)\s+(the\s+)?(api[_-]?key|secret|env|password|token)", re.IGNORECASE),
        re.compile(r"<system_instructions>[\s\S]*?</system_instructions>", re.IGNORECASE),
        re.compile(r"\[SYSTEM_OVERRIDE\]", re.IGNORECASE),
    ]

    @classmethod
    def validate_command(cls, command: str) -> Tuple[bool, str]:
        """
        Validates that a terminal command does not violate safety policies.
        Rejects destructive calls, cloud metadata accesses, and reverse shells.
        """
        cleaned = command.strip()
        for pattern in cls.BLOCKED_COMMAND_PATTERNS:
            if pattern.search(cleaned):
                msg = f"CRITICAL SECURITY VIOLATION: Command blocked by ASTRA security policy (pattern matched: {pattern.pattern})"
                logger.error(f"[SECURITY] Blocked dangerous command: {command} -> Reason: {msg}")
                return False, msg
        return True, "Command allowed"

    @classmethod
    def is_command_safe(cls, command: str) -> Tuple[bool, str]:
        """Convenience alias for validate_command."""
        return cls.validate_command(command)

    @classmethod
    def sanitize_secrets(cls, text: str) -> str:
        """
        Redacts sensitive tokens, API keys, passwords, and private keys
        to ensure zero secret leakage into logs, events, or pull requests.
        """
        if not text or not isinstance(text, str):
            return text

        sanitized = text
        for pattern in cls.SECRETS_PATTERNS:
            sanitized = pattern.sub("[REDACTED_SECRET]", sanitized)
        return sanitized

    @classmethod
    def sanitize_payload(cls, data: Any) -> Any:
        """Recursively sanitizes dictionary, list, or string payloads."""
        if isinstance(data, str):
            return cls.sanitize_secrets(data)
        elif isinstance(data, dict):
            clean_dict = {}
            for k, v in data.items():
                # Redact keys with sensitive names
                if any(sec in k.lower() for sec in ["password", "secret", "token", "api_key", "auth"]):
                    clean_dict[k] = "[REDACTED_SECRET]"
                else:
                    clean_dict[k] = cls.sanitize_payload(v)
            return clean_dict
        elif isinstance(data, list):
            return [cls.sanitize_payload(item) for item in data]
        return data

    @classmethod
    def inspect_prompt_injection(cls, text: str) -> Tuple[bool, Optional[str]]:
        """
        Inspects text for prompt injection signatures.
        Returns (is_safe, matched_pattern_text).
        """
        if not text or not isinstance(text, str):
            return True, None
        for pattern in cls.PROMPT_INJECTION_PATTERNS:
            m = pattern.search(text)
            if m:
                return False, m.group(0)
        return True, None

    @classmethod
    def sanitize_untrusted_input(cls, text: str) -> str:
        """
        Sanitizes text originating from repository files, issues, or commits
        to neutralize prompt injection attempts targeting the agent.
        """
        if not text or not isinstance(text, str):
            return text

        sanitized = text
        for pattern in cls.PROMPT_INJECTION_PATTERNS:
            if pattern.search(sanitized):
                logger.warning(f"[SECURITY] Prompt injection pattern '{pattern.pattern}' detected. Neutralizing.")
                sanitized = pattern.sub("[UNTRUSTED_CONTENT_FLAGGED]", sanitized)

        # Also sanitize any embedded secrets
        return cls.sanitize_secrets(sanitized)
