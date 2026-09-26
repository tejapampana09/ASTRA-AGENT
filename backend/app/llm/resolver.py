from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from app.config import settings
from app.observability.logging import logger


@dataclass
class ResolvedModel:
    model: str
    provider: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.1
    timeout: int = 120
    drop_params: bool = True

    def to_dict(self) -> dict:
        return {
            "model": self.model,
            "provider": self.provider,
            "base_url": self.base_url,
            "temperature": self.temperature,
            "timeout": self.timeout,
        }


def resolve_model(
    requested_model: Optional[str] = None,
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> ResolvedModel:
    """
    Canonical LLM model resolver for ASTRA 2.0.
    Unifies model resolution across CLI, Task Lifecycle, LangGraph Executor, and AgentRuntime.
    
    Supported providers:
    - Gemini (Google AI Studio)
    - Ollama (Local)
    - OpenRouter
    - Anthropic
    - OpenAI
    """
    raw = (requested_model or "").strip()
    prov = (provider or "").strip().lower()

    # 1. Explicit Ollama / Local requests
    if (
        prov == "ollama"
        or "ollama" in raw.lower()
        or "qwen" in raw.lower()
        or raw.lower() in ["local", "ollama-local"]
    ):
        model_name = raw if "/" in raw else f"ollama/{raw}" if raw and raw not in ["local", "ollama"] else "ollama/qwen2.5-coder:3b"
        effective_base_url = base_url or os.environ.get("LLM_BASE_URL") or "http://localhost:11434"
        logger.info(f"Resolved model: {model_name} (provider=ollama, base_url={effective_base_url})")
        return ResolvedModel(
            model=model_name,
            provider="ollama",
            api_key="ollama-local",
            base_url=effective_base_url,
            timeout=max(300, settings.LLM_TIMEOUT_SECONDS),
            drop_params=True,
        )

    # 2. Explicit Gemini requests
    if prov == "gemini" or "gemini" in raw.lower() or raw.lower() in ["flash", "cloud"]:
        key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("LLM_API_KEY")
        if "/" in raw:
            model_name = raw
        elif raw and raw not in ["flash", "cloud", "gemini"]:
            model_name = f"gemini/{raw}"
        else:
            model_name = os.environ.get("GEMINI_MODEL") or "gemini/gemini-2.5-flash"

        logger.info(f"Resolved model: {model_name} (provider=gemini)")
        return ResolvedModel(
            model=model_name,
            provider="gemini",
            api_key=key,
            base_url=None,
            timeout=settings.LLM_TIMEOUT_SECONDS,
            drop_params=True,
        )

    # 3. Explicit OpenRouter requests
    if prov == "openrouter" or "openrouter" in raw.lower():
        key = api_key or os.environ.get("OPENROUTER_API_KEY") or os.environ.get("LLM_API_KEY")
        model_name = raw if "/" in raw else f"openrouter/{raw}"
        effective_base_url = base_url or os.environ.get("LLM_BASE_URL") or "https://openrouter.ai/api/v1"
        logger.info(f"Resolved model: {model_name} (provider=openrouter)")
        return ResolvedModel(
            model=model_name,
            provider="openrouter",
            api_key=key,
            base_url=effective_base_url,
            timeout=settings.LLM_TIMEOUT_SECONDS,
            drop_params=True,
        )

    # 4. Explicit Anthropic requests
    if prov == "anthropic" or "anthropic" in raw.lower() or "claude" in raw.lower():
        key = api_key or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("LLM_API_KEY")
        model_name = raw if "/" in raw else f"anthropic/{raw}" if raw else "anthropic/claude-3-5-sonnet-20241022"
        logger.info(f"Resolved model: {model_name} (provider=anthropic)")
        return ResolvedModel(
            model=model_name,
            provider="anthropic",
            api_key=key,
            base_url=None,
            timeout=settings.LLM_TIMEOUT_SECONDS,
            drop_params=True,
        )

    # 5. Explicit OpenAI requests
    if prov == "openai" or "openai" in raw.lower() or "gpt" in raw.lower():
        key = api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")
        model_name = raw if "/" in raw else f"openai/{raw}" if raw else "openai/gpt-4o"
        logger.info(f"Resolved model: {model_name} (provider=openai)")
        return ResolvedModel(
            model=model_name,
            provider="openai",
            api_key=key,
            base_url=None,
            timeout=settings.LLM_TIMEOUT_SECONDS,
            drop_params=True,
        )

    # 6. Auto-detect from environment or fallback to defaults
    env_model = os.environ.get("LLM_MODEL")
    if env_model:
        return resolve_model(requested_model=env_model, api_key=api_key, base_url=base_url)

    if os.environ.get("GEMINI_API_KEY"):
        return resolve_model(requested_model="gemini/gemini-2.5-flash", api_key=os.environ.get("GEMINI_API_KEY"))

    if os.environ.get("OPENROUTER_API_KEY"):
        return resolve_model(
            requested_model="openrouter/anthropic/claude-3.5-sonnet",
            api_key=os.environ.get("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1"
        )

    if os.environ.get("ANTHROPIC_API_KEY"):
        return resolve_model(
            requested_model="anthropic/claude-3-5-sonnet-20241022",
            api_key=os.environ.get("ANTHROPIC_API_KEY")
        )

    if os.environ.get("OPENAI_API_KEY"):
        return resolve_model(
            requested_model="openai/gpt-4o",
            api_key=os.environ.get("OPENAI_API_KEY")
        )

    # Default fallback: Local Ollama
    return resolve_model(requested_model="ollama/qwen2.5-coder:3b")
