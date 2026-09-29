"""Unified LLM provider interface for ASTRA with fast health-checks and zero hangs."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional
from astra.config import settings


class LLMResponse:
    def __init__(self, content: str = "", tool_calls: Optional[List[Dict[str, Any]]] = None, raw_content: Any = None):
        self.content = content
        self.tool_calls = tool_calls or []
        self.raw_content = raw_content

    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


def check_endpoint_health(url: str, timeout: int = 4) -> bool:
    """Fast check to ensure custom endpoint or server is actually online."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ASTRA/3.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status < 500
    except Exception:
        return False


class LLMClient:
    """Client for routing completions to TejaAI GPU Server, Gemini, LiteLLM, or Ollama."""

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.default_model

    def complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.1,
    ) -> LLMResponse:
        """Synchronous chat completion with automatic provider dispatch."""
        model = (self.model_name or "").lower()

        # 1. Custom TejaAI Model Server (Colab GPU)
        if "teja" in model or "colab" in model or (settings.teja_model_url and "gemma" in model):
            return self._call_teja_gpu_server(messages, tools, temperature)

        # 2. Gemini API
        if "gemini" in model or not (settings.openai_api_key or settings.anthropic_api_key):
            if settings.gemini_api_key or "gemini" in model:
                return self._call_gemini(messages, tools, temperature)

        # 3. LiteLLM (OpenAI, Claude, Ollama, OpenRouter, etc.)
        return self._call_litellm(messages, tools, temperature)

    def _call_teja_gpu_server(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.1,
    ) -> LLMResponse:
        """Call TejaAI GPU endpoint directly with instant failure reporting."""
        url = settings.teja_model_url.strip()
        if not url:
            raise ValueError(
                "TEJA_MODEL_URL is not set in .env. Please configure your Colab Cloudflare URL or switch model: /model gemini"
            )

        # Root health check
        base_url = url.replace("/v1", "").rstrip("/")
        if not check_endpoint_health(f"{base_url}/health", timeout=4):
            raise ConnectionError(
                f"TejaAI GPU server is offline or unreachable at '{url}'.\n"
                "Please verify your Colab notebook & Cloudflare tunnel are running, or switch model: /model gemini"
            )

        # Build clean message history tailored for fine-tuned Gemma 2B
        clean_messages = []
        for m in messages:
            content = m.get("content") or ""
            role = m.get("role", "user")

            if role == "system":
                # 2B models perform best with simple, direct instructions
                content = "You are an expert AI software developer. Directly solve the user's task and write clean, correct, working code."
            elif role == "user":
                # Strip bulky workspace headers if present so 2B model isn't confused
                if "Task Goal:\n" in content:
                    content = content.split("Task Goal:\n")[-1].strip()
            elif role == "tool":
                role = "user"
                content = f"[Tool Result]:\n{content}"
            elif role == "assistant" and not content and m.get("tool_calls"):
                content = f"[Executing Tools: {', '.join(tc.get('function', {}).get('name', '') for tc in m['tool_calls'])}]"

            clean_messages.append({"role": role, "content": str(content)})

        # Endpoint URL
        completions_url = f"{url.rstrip('/')}/chat/completions"
        payload = {
            "model": "teja-ai-gemma4-e2b",
            "messages": clean_messages,
            "temperature": temperature,
            "max_tokens": 512,
        }

        try:
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                completions_url,
                data=req_data,
                headers={"Content-Type": "application/json", "User-Agent": "ASTRA/3.0"},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                choice = data.get("choices", [{}])[0]
                content = choice.get("message", {}).get("content", "").strip()
                return LLMResponse(content=content)
        except urllib.error.HTTPError as http_err:
            try:
                err_body = http_err.read().decode("utf-8")
                detail = json.loads(err_body).get("detail", err_body)
            except Exception:
                detail = str(http_err)
            raise RuntimeError(f"Colab GPU Server Error ({http_err.code}): {detail}")
        except Exception as exc:
            raise RuntimeError(f"Failed to communicate with Colab GPU server: {exc}")

    def _call_gemini(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.1,
    ) -> LLMResponse:
        """Call Google Gemini using google-genai."""
        api_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set. Please set GEMINI_API_KEY in your .env file or environment, "
                "or switch model via /model teja-gemma."
            )

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            model_id = "gemini-3.5-flash"
            if "lite" in self.model_name:
                model_id = "gemini-3.5-flash-lite"
            elif self.model_name and self.model_name != "gemini":
                if "3.8" in self.model_name:
                    model_id = "gemini-3.8-flash"
                elif "pro" in self.model_name:
                    model_id = "gemini-3.5-pro"
                elif "gemini" in self.model_name:
                    model_id = self.model_name

            gemini_contents = []
            system_instruction = None

            for msg in messages:
                role = msg.get("role")
                content = msg.get("content") or ""

                if role == "system":
                    system_instruction = content
                elif role == "user":
                    gemini_contents.append(types.Content(role="user", parts=[types.Part.from_text(text=content)]))
                elif role == "assistant":
                    if msg.get("raw_content"):
                        gemini_contents.append(msg["raw_content"])
                    else:
                        parts = []
                        if content:
                            parts.append(types.Part.from_text(text=content))
                        for tc in msg.get("tool_calls", []):
                            fn = tc.get("function", {})
                            args = fn.get("arguments", {})
                            if isinstance(args, str):
                                try:
                                    args = json.loads(args)
                                except Exception:
                                    pass
                            parts.append(types.Part.from_function_call(name=fn.get("name"), args=args))
                        gemini_contents.append(types.Content(role="model", parts=parts))
                elif role == "tool":
                    fn_name = msg.get("name", "tool")
                    raw_out = content if isinstance(content, str) else json.dumps(content)
                    gemini_contents.append(
                        types.Content(
                            role="user",
                            parts=[types.Part.from_function_response(name=fn_name, response={"result": raw_out})],
                        )
                    )

            genai_tools = []
            if tools:
                declarations = []
                for t in tools:
                    declarations.append(
                        types.FunctionDeclaration(
                            name=t["name"],
                            description=t.get("description", ""),
                            parameters=t.get("parameters"),
                        )
                    )
                genai_tools.append(types.Tool(function_declarations=declarations))

            config = types.GenerateContentConfig(
                temperature=temperature,
                system_instruction=system_instruction,
                tools=genai_tools if genai_tools else None,
            )

            response = client.models.generate_content(
                model=model_id,
                contents=gemini_contents,
                config=config,
            )

            text_content = ""
            tool_calls = []

            if response.candidates:
                candidate = response.candidates[0]
                if candidate.content and candidate.content.parts:
                    for part in candidate.content.parts:
                        if part.text:
                            text_content += part.text
                        if part.function_call:
                            fn = part.function_call
                            tool_calls.append(
                                {
                                    "id": getattr(fn, "id", None) or f"call_{fn.name}",
                                    "type": "function",
                                    "function": {
                                        "name": fn.name,
                                        "arguments": fn.args if isinstance(fn.args, dict) else {},
                                    },
                                }
                            )

            raw_content = response.candidates[0].content if response.candidates else None
            return LLMResponse(content=text_content, tool_calls=tool_calls, raw_content=raw_content)
        except Exception as exc:
            raise RuntimeError(f"Gemini API error ({self.model_name}): {exc}")

    def _call_litellm(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.1,
    ) -> LLMResponse:
        """Call models via LiteLLM."""
        import litellm

        litellm.suppress_debug_info = True
        litellm.set_verbose = False

        openai_tools = None
        if tools:
            openai_tools = [{"type": "function", "function": t} for t in tools]

        kwargs: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
        }
        if openai_tools:
            kwargs["tools"] = openai_tools

        try:
            resp = litellm.completion(**kwargs)
            choice = resp.choices[0]
            message = choice.message

            content = message.content or ""
            tool_calls = []

            if hasattr(message, "tool_calls") and message.tool_calls:
                for tc in message.tool_calls:
                    fn_name = tc.function.name
                    raw_args = tc.function.arguments
                    parsed_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    tool_calls.append(
                        {
                            "id": getattr(tc, "id", None) or f"call_{fn_name}",
                            "type": "function",
                            "function": {"name": fn_name, "arguments": parsed_args},
                        }
                    )

            return LLMResponse(content=content, tool_calls=tool_calls)
        except Exception as exc:
            raise RuntimeError(f"LLM completion error ({self.model_name}): {exc}")
