from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional


@dataclass
class LLMMessage:
    role: str  # "system", "user", "assistant", "tool"
    content: str
    name: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None


@dataclass
class LLMResponse:
    content: str
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    raw_response: Optional[Any] = None


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def chat(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        **kwargs: Any
    ) -> LLMResponse:
        """Send chat messages and return a full response."""
        pass

    @abstractmethod
    async def stream(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.1,
        **kwargs: Any
    ) -> AsyncIterator[str]:
        """Stream response tokens asynchronously."""
        pass

    @abstractmethod
    async def structured_output(
        self,
        messages: List[LLMMessage],
        response_model: type,
        **kwargs: Any
    ) -> Any:
        """Return validated Pydantic model response."""
        pass
