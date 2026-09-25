from __future__ import annotations

import os
from typing import Any, AsyncIterator, Dict, List, Optional
import litellm

from app.config import settings
from app.llm.base import LLMMessage, LLMProvider, LLMResponse
from app.observability.logging import logger


class LiteLLMProvider(LLMProvider):
    """Universal LLM Provider implemented via LiteLLM."""

    def __init__(self, model_name: str, api_key: Optional[str] = None):
        self.model = model_name
        self.api_key = api_key or settings.LLM_API_KEY or os.environ.get("LLM_API_KEY")

    async def chat(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        **kwargs: Any
    ) -> LLMResponse:
        msgs = [{"role": m.role, "content": m.content} for m in messages]
        resp = await litellm.acompletion(
            model=self.model,
            messages=msgs,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=self.api_key,
            **kwargs
        )
        choice = resp.choices[0]
        content = choice.message.content or ""
        usage = getattr(resp, "usage", None)

        return LLMResponse(
            content=content,
            model=self.model,
            prompt_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
            raw_response=resp
        )

    async def stream(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.1,
        **kwargs: Any
    ) -> AsyncIterator[str]:
        msgs = [{"role": m.role, "content": m.content} for m in messages]
        stream_resp = await litellm.acompletion(
            model=self.model,
            messages=msgs,
            temperature=temperature,
            stream=True,
            api_key=self.api_key,
            **kwargs
        )
        async for chunk in stream_resp:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                yield delta

    async def structured_output(
        self,
        messages: List[LLMMessage],
        response_model: type,
        **kwargs: Any
    ) -> Any:
        # LiteLLM instructor / response_format
        msgs = [{"role": m.role, "content": m.content} for m in messages]
        resp = await litellm.acompletion(
            model=self.model,
            messages=msgs,
            response_format=response_model,
            api_key=self.api_key,
            **kwargs
        )
        content = resp.choices[0].message.content
        if hasattr(response_model, "model_validate_json"):
            return response_model.model_validate_json(content)
        return content


class LLMRouter:
    """
    Routes LLM operations to specific model profiles:
    - 'fast': fast summaries, classification, intent extraction
    - 'coding': code generation, patching, test creation
    - 'reasoning': architectural planning, deep debugging, root cause analysis
    """

    def __init__(self):
        self.profiles: Dict[str, str] = {
            "fast": settings.ROUTER_FAST_MODEL,
            "coding": settings.ROUTER_CODING_MODEL,
            "reasoning": settings.ROUTER_REASONING_MODEL,
        }

    def get_provider(self, profile: str = "coding") -> LLMProvider:
        model = self.profiles.get(profile, settings.LLM_MODEL)
        return LiteLLMProvider(model_name=model)


# Global router singleton
llm_router = LLMRouter()
