"""ASTRA V4 Modular LLM Provider Interface & Router.

Provides first-class Ollama support alongside Gemini, TejaAI, Groq, and OpenAI-compatible providers.
All providers support structured tool-calling, health checks, model discovery, and streaming.
"""
from __future__ import annotations

import abc
import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple, Union
from astra.config import settings


class LLMResponse:
    """Standardized response from any LLM provider."""

    def __init__(
        self,
        content: str = "",
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        raw_content: Any = None,
        provider: str = "",
        model: str = "",
    ):
        self.content = content or ""
        self.tool_calls = tool_calls or []
        self.raw_content = raw_content
        self.provider = provider
        self.model = model

    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "tool_calls": self.tool_calls,
            "provider": self.provider,
            "model": self.model,
        }

    def __repr__(self) -> str:
        return f"<LLMResponse provider={self.provider} model={self.model} tools={len(self.tool_calls)} content_len={len(self.content)}>"


def check_endpoint_health(url: str, timeout: int = 3) -> bool:
    """Fast check to ensure custom endpoint or server is actually online."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ASTRA/4.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status < 500
    except Exception:
        return False


def parse_tool_calls_from_text(text: str) -> Tuple[str, List[Dict[str, Any]]]:
    """Universal parser for models that output tool calls in markdown or special tokens."""
    tool_calls: List[Dict[str, Any]] = []
    cleaned_text = text

    # Pattern 1: Gemma special token syntax: <|tool_call>call:name{args}<tool_call|>
    token_pattern = re.compile(r"<\|tool_call\>call:(\w+)(\{.*?\})<tool_call\|\>", re.DOTALL)
    for match in token_pattern.finditer(text):
        fn_name = match.group(1)
        raw_args = match.group(2)
        try:
            parsed_args = json.loads(raw_args)
        except Exception:
            parsed_args = {}
        tool_calls.append({
            "id": f"call_{fn_name}",
            "type": "function",
            "function": {"name": fn_name, "arguments": parsed_args},
        })
    if tool_calls:
        cleaned_text = token_pattern.sub("", text).strip()
        return cleaned_text, tool_calls

    # Pattern 2: Markdown ```json blocks
    json_block_pattern = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
    for match in json_block_pattern.finditer(text):
        raw_json = match.group(1).strip()
        try:
            data = json.loads(raw_json)
            fn_name = data.get("name") or data.get("tool") or data.get("function")
            if fn_name and isinstance(fn_name, str):
                fn_args = data.get("arguments") or data.get("args") or data.get("parameters") or {}
                if isinstance(fn_args, str):
                    try:
                        fn_args = json.loads(fn_args)
                    except Exception:
                        fn_args = {}
                tool_calls.append({
                    "id": f"call_{fn_name}",
                    "type": "function",
                    "function": {"name": fn_name, "arguments": fn_args},
                })
        except Exception:
            pass

    if tool_calls:
        cleaned_text = json_block_pattern.sub("", text).strip()
        return cleaned_text, tool_calls

    # Pattern 3: Standalone or nested JSON objects with "name" and "arguments" / "parameters"
    decoder = json.JSONDecoder()
    idx = 0
    matched_spans = []
    while idx < len(text):
        start = text.find("{", idx)
        if start == -1:
            break
        try:
            obj, end_offset = decoder.raw_decode(text[start:])
            end_pos = start + end_offset
            if isinstance(obj, dict):
                fn_name = obj.get("name") or obj.get("tool") or obj.get("function")
                if fn_name and isinstance(fn_name, str):
                    fn_args = obj.get("arguments") or obj.get("args") or obj.get("parameters") or {}
                    if isinstance(fn_args, str):
                        try:
                            fn_args = json.loads(fn_args)
                        except Exception:
                            fn_args = {}
                    tool_calls.append({
                        "id": f"call_{fn_name}_{len(tool_calls)+1}",
                        "type": "function",
                        "function": {"name": fn_name, "arguments": fn_args},
                    })
                    matched_spans.append((start, end_pos))
            idx = end_pos
        except json.JSONDecodeError:
            idx = start + 1

    if tool_calls:
        # Remove matched tool JSON chunks from text
        cleaned_chars = list(text)
        for s, e in reversed(matched_spans):
            cleaned_chars[s:e] = []
        cleaned_text = "".join(cleaned_chars).strip()
        return cleaned_text, tool_calls

    return text.strip(), []


# Backward compatibility alias
parse_gemma_tool_calls = parse_tool_calls_from_text


class LLMProvider(abc.ABC):
    """Abstract Base Class for all LLM Providers in ASTRA V4."""

    @abc.abstractmethod
    def complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.1,
        model: Optional[str] = None,
    ) -> LLMResponse:
        """Synchronous chat completion with tool calling."""
        pass

    @abc.abstractmethod
    def health(self) -> Dict[str, Any]:
        """Check provider health and connection status."""
        pass

    @abc.abstractmethod
    def list_models(self) -> List[Dict[str, Any]]:
        """List available models for this provider."""
        pass


class OllamaProvider(LLMProvider):
    """First-Class Ollama Provider.
    
    Communicates directly with Ollama daemon on http://localhost:11434.
    Supports tool calling, model discovery, and connection status.
    """

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or settings.ollama_base_url or "http://localhost:11434").rstrip("/")

    def health(self) -> Dict[str, Any]:
        """Check if local Ollama daemon is active and reachable."""
        try:
            url = f"{self.base_url}/api/version"
            req = urllib.request.Request(url, headers={"User-Agent": "ASTRA/4.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    return {
                        "connected": True,
                        "status": "connected",
                        "version": data.get("version", "unknown"),
                        "endpoint": self.base_url,
                        "message": "Ollama is running and connected.",
                    }
        except Exception as exc:
            pass
            
        # Try /api/tags fallback
        try:
            url = f"{self.base_url}/api/tags"
            req = urllib.request.Request(url, headers={"User-Agent": "ASTRA/4.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    return {
                        "connected": True,
                        "status": "connected",
                        "endpoint": self.base_url,
                        "message": "Ollama is running and connected.",
                    }
        except Exception as exc:
            return {
                "connected": False,
                "status": "disconnected",
                "endpoint": self.base_url,
                "error": str(exc),
                "message": (
                    "Ollama is disconnected or not running. "
                    "Start Ollama with 'ollama serve' or launch the Ollama desktop app, "
                    "or run 'ollama pull qwen2.5-coder:7b'."
                ),
            }

        return {
            "connected": False,
            "status": "disconnected",
            "endpoint": self.base_url,
            "message": "Ollama daemon unreachable.",
        }

    def list_models(self) -> List[Dict[str, Any]]:
        """Query Ollama daemon for currently installed models."""
        try:
            url = f"{self.base_url}/api/tags"
            req = urllib.request.Request(url, headers={"User-Agent": "ASTRA/4.0"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = []
                for m in data.get("models", []):
                    name = m.get("name")
                    size = m.get("size", 0)
                    size_gb = f"{size / (1024**3):.1f} GB" if size else ""
                    models.append({
                        "id": name,
                        "name": name,
                        "provider": "ollama",
                        "size": size_gb,
                        "details": m.get("details", {}),
                    })
                return models
        except Exception:
            return []

    def complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.1,
        model: Optional[str] = None,
    ) -> LLMResponse:
        """Call Ollama chat API with tool definitions."""
        model_name = model or settings.default_model
        if model_name.startswith("ollama/"):
            model_name = model_name[len("ollama/"):]

        # Verify connection first
        h = self.health()
        if not h.get("connected"):
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.base_url}.\n"
                f"Details: {h.get('message')}"
            )

        # Build tools structure formatted for Ollama
        ollama_tools = None
        if tools:
            ollama_tools = []
            for t in tools:
                ollama_tools.append({
                    "type": "function",
                    "function": {
                        "name": t.get("name"),
                        "description": t.get("description", ""),
                        "parameters": t.get("parameters", {}),
                    }
                })

        # Format messages for Ollama /api/chat
        formatted_messages = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content") or ""
            msg: Dict[str, Any] = {"role": role, "content": str(content)}
            if role == "assistant" and m.get("tool_calls"):
                msg["tool_calls"] = m["tool_calls"]
            formatted_messages.append(msg)

        payload: Dict[str, Any] = {
            "model": model_name,
            "messages": formatted_messages,
            "stream": False,
            "keep_alive": "15m",
            "options": {
                "temperature": temperature,
                "num_ctx": 4096,
                "num_predict": 1024,
            },
        }
        if ollama_tools:
            payload["tools"] = ollama_tools

        url = f"{self.base_url}/api/chat"
        req_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=req_data,
            headers={"Content-Type": "application/json", "User-Agent": "ASTRA/4.0"},
        )

        ollama_timeout = max(getattr(settings, "timeout_seconds", 300), 300)
        try:
            with urllib.request.urlopen(req, timeout=ollama_timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                msg = data.get("message", {})
                content = msg.get("content", "")
                raw_tool_calls = msg.get("tool_calls", [])

                parsed_tool_calls = []
                for tc in raw_tool_calls:
                    fn = tc.get("function", {})
                    fn_name = fn.get("name")
                    fn_args = fn.get("arguments", {})
                    if isinstance(fn_args, str):
                        try:
                            fn_args = json.loads(fn_args)
                        except Exception:
                            fn_args = {}
                    parsed_tool_calls.append({
                        "id": f"call_ollama_{fn_name}",
                        "type": "function",
                        "function": {"name": fn_name, "arguments": fn_args},
                    })

                # If Ollama didn't return native tool calls but content contains tool call tokens/json
                if not parsed_tool_calls and content:
                    content, parsed_tool_calls = parse_tool_calls_from_text(content)

                return LLMResponse(
                    content=content,
                    tool_calls=parsed_tool_calls,
                    raw_content=data,
                    provider="ollama",
                    model=model_name,
                )
        except urllib.error.HTTPError as http_err:
            try:
                body = http_err.read().decode("utf-8")
                err_json = json.loads(body)
                msg = err_json.get("error", body)
            except Exception:
                msg = str(http_err)
            raise RuntimeError(f"Ollama API Error ({http_err.code}): {msg}")
        except Exception as exc:
            raise RuntimeError(f"Ollama communication error: {exc}")


class GeminiProvider(LLMProvider):
    """Google Gemini Provider using modern google-genai SDK."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.gemini_api_key

    def health(self) -> Dict[str, Any]:
        connected = bool(self.api_key)
        return {
            "connected": connected,
            "status": "connected" if connected else "missing_key",
            "provider": "gemini",
            "message": "Gemini API key is configured." if connected else "GEMINI_API_KEY is not set.",
        }

    def list_models(self) -> List[Dict[str, Any]]:
        return [
            {"id": "gemini-3.8-flash", "name": "Gemini 3.8 Flash (Google Brain - Fast & Smart)", "provider": "gemini"},
            {"id": "gemini-2.5-pro", "name": "Gemini 2.5 Pro (Deep Reasoning)", "provider": "gemini"},
        ]

    def complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.1,
        model: Optional[str] = None,
    ) -> LLMResponse:
        api_key = self.api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set. Please set it in .env or switch to Ollama.")

        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        model_id = model or "gemini-3.8-flash"
        if model_id.startswith("gemini/"):
            model_id = model_id[len("gemini/"):]
        if not model_id.startswith("gemini-"):
            model_id = "gemini-3.8-flash"

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
        return LLMResponse(content=text_content, tool_calls=tool_calls, raw_content=raw_content, provider="gemini", model=model_id)


class TejaAIProvider(LLMProvider):
    """TejaAI fine-tuned Gemma server on Colab/Kaggle GPU with Cloudflare tunnel."""

    def __init__(self, endpoint_url: Optional[str] = None):
        self.endpoint_url = (endpoint_url or settings.teja_model_url or "").rstrip("/")

    def health(self) -> Dict[str, Any]:
        if not self.endpoint_url:
            return {"connected": False, "status": "no_url", "message": "TEJA_MODEL_URL is not configured in .env."}
        base_url = self.endpoint_url.replace("/v1", "").rstrip("/")
        online = check_endpoint_health(f"{base_url}/health", timeout=3)
        return {
            "connected": online,
            "status": "connected" if online else "disconnected",
            "provider": "teja",
            "endpoint": self.endpoint_url,
            "message": "TejaAI GPU server is online." if online else "TejaAI GPU server unreachable.",
        }

    def list_models(self) -> List[Dict[str, Any]]:
        return [
            {"id": "teja-ai-gemma4-e2b", "name": "TejaAI Gemma-4 2B (Fine-Tuned)", "provider": "teja"},
        ]

    def complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.1,
        model: Optional[str] = None,
    ) -> LLMResponse:
        url = self.endpoint_url.strip()
        if not url:
            raise ValueError("TEJA_MODEL_URL is not set in .env.")

        base_url = url.replace("/v1", "").rstrip("/")
        if not check_endpoint_health(f"{base_url}/health", timeout=4):
            raise ConnectionError(f"TejaAI GPU server is offline or unreachable at '{url}'.")

        tools_prompt = ""
        if tools:
            tool_descs = []
            for t in tools:
                props = t.get("parameters", {}).get("properties", {})
                reqs = t.get("parameters", {}).get("required", [])
                param_strs = [f"{p} ({props[p].get('type', 'any')}){' [required]' if p in reqs else ''}: {props[p].get('description', '')}" for p in props]
                params_joined = "; ".join(param_strs)
                tool_descs.append(f"- `{t['name']}`: {t.get('description', '')}\n  Args: {params_joined}")

            tools_prompt = (
                "\n\nYou have access to the following tools to inspect and modify the codebase:\n"
                + "\n".join(tool_descs)
                + "\n\nWhen you need to call a tool, respond with a JSON block in this exact format:\n"
                + "```json\n"
                + '{"name": "tool_name", "arguments": {"arg_key": "arg_value"}}\n'
                + "```\n"
                + "When you have completed the task and verified it, summarize your solution without calling any more tools."
            )

        clean_messages = []
        for m in messages:
            content = m.get("content") or ""
            role = m.get("role", "user")

            if role == "system":
                content = (
                    "You are ASTRA, an elite autonomous software engineering agent. "
                    "Directly solve the user's task with clean, correct, working code."
                    + tools_prompt
                )
            elif role == "user":
                if "Task Goal:\n" in content:
                    content = content.split("Task Goal:\n")[-1].strip()
            elif role == "tool":
                role = "user"
                fn_name = m.get("name", "tool")
                content = f"[Tool Result for '{fn_name}']:\n{content}"
            elif role == "assistant" and not content and m.get("tool_calls"):
                fn_calls = [tc.get("function", {}).get("name", "") for tc in m["tool_calls"]]
                content = f"Calling tools: {', '.join(fn_calls)}"

            clean_messages.append({"role": role, "content": str(content)})

        completions_url = f"{url.rstrip('/')}/chat/completions"
        payload = {
            "model": model or "teja-ai-gemma4-e2b",
            "messages": clean_messages,
            "temperature": temperature,
            "max_tokens": 512,
        }

        try:
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                completions_url,
                data=req_data,
                headers={"Content-Type": "application/json", "User-Agent": "ASTRA/4.0"},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                choice = data.get("choices", [{}])[0]
                raw_text = choice.get("message", {}).get("content", "").strip()
                thought, tool_calls = parse_gemma_tool_calls(raw_text)
                return LLMResponse(content=thought or raw_text, tool_calls=tool_calls, raw_content=data, provider="teja", model="teja-gemma")
        except Exception as exc:
            raise RuntimeError(f"TejaAI GPU server error: {exc}")


class GroqProvider(LLMProvider):
    """Groq Provider for ultra-fast Llama 3.3 / Qwen models."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.groq_api_key

    def health(self) -> Dict[str, Any]:
        connected = bool(self.api_key)
        return {
            "connected": connected,
            "status": "connected" if connected else "missing_key",
            "provider": "groq",
            "message": "Groq API key configured (14.4k req/day free)." if connected else "GROQ_API_KEY is not set.",
        }

    def list_models(self) -> List[Dict[str, Any]]:
        return [
            {"id": "qwen/qwen3.8-27b", "name": "Qwen 3.8 27B (Groq - 27B Fast)", "provider": "groq"},
            {"id": "openai/gpt-oss-120b", "name": "GPT-OSS 120B (Groq - Massive 120B)", "provider": "groq"},
            {"id": "openai/gpt-oss-20b", "name": "GPT-OSS 20B (Groq)", "provider": "groq"},
        ]

    def complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.1,
        model: Optional[str] = None,
    ) -> LLMResponse:
        api_key = self.api_key or os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY is not set in .env.")

        model_id = "qwen/qwen3.8-27b"
        if model:
            m_clean = model
            if m_clean.startswith("groq/"):
                m_clean = m_clean[len("groq/"):]
            if "120b" in m_clean.lower():
                model_id = "openai/gpt-oss-120b"
            elif "20b" in m_clean.lower():
                model_id = "openai/gpt-oss-20b"
            elif "qwen" in m_clean.lower():
                model_id = "qwen/qwen3.8-27b"
            elif m_clean in ["qwen/qwen3.8-27b", "openai/gpt-oss-120b", "openai/gpt-oss-20b"]:
                model_id = m_clean

        formatted_messages = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content") or ""
            msg_dict: Dict[str, Any] = {"role": role, "content": content}

            if role == "assistant" and m.get("tool_calls"):
                serialized_calls = []
                for tc in m["tool_calls"]:
                    fn = tc.get("function", {})
                    args = fn.get("arguments", {})
                    args_str = json.dumps(args) if isinstance(args, dict) else str(args)
                    serialized_calls.append({
                        "id": tc.get("id") or f"call_{fn.get('name')}",
                        "type": "function",
                        "function": {
                            "name": fn.get("name"),
                            "arguments": args_str,
                        },
                    })
                msg_dict["tool_calls"] = serialized_calls
            elif role == "tool":
                msg_dict["tool_call_id"] = m.get("tool_call_id") or f"call_{m.get('name', 'tool')}"
                msg_dict["name"] = m.get("name", "tool")

            formatted_messages.append(msg_dict)

        payload: Dict[str, Any] = {
            "model": model_id,
            "messages": formatted_messages,
            "temperature": temperature,
            "max_tokens": 4096,
        }

        if tools:
            payload["tools"] = [{"type": "function", "function": t} for t in tools]
            payload["tool_choice"] = "auto"

        url = "https://api.groq.com/openai/v1/chat/completions"
        req_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=req_data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                choice = data.get("choices", [{}])[0]
                message = choice.get("message", {})
                content = message.get("content") or ""
                raw_tool_calls = message.get("tool_calls") or []

                tool_calls = []
                for tc in raw_tool_calls:
                    fn = tc.get("function", {})
                    raw_args = fn.get("arguments", {})
                    parsed_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    tool_calls.append({
                        "id": tc.get("id") or f"call_{fn.get('name')}",
                        "type": "function",
                        "function": {"name": fn.get("name"), "arguments": parsed_args},
                    })

        except Exception as exc:
            err_str = str(exc)
            if "429" in err_str or "too many requests" in err_str.lower() or "rate" in err_str.lower():
                if getattr(settings, "gemini_api_key", None):
                    try:
                        gemini = GeminiProvider()
                        return gemini.complete(messages=messages, tools=tools, temperature=temperature)
                    except Exception:
                        pass
                try:
                    ollama = OllamaProvider()
                    return ollama.complete(messages=messages, tools=tools, temperature=temperature)
                except Exception:
                    pass
            raise RuntimeError(f"Groq API error: {exc}")


class LLMRouter:
    """Central router that delegates to Ollama, Gemini, Groq, TejaAI, or LiteLLM."""

    def __init__(self):
        self.ollama = OllamaProvider()
        self.gemini = GeminiProvider()
        self.groq = GroqProvider()
        self.teja = TejaAIProvider()

    def get_provider_and_model(self, model_spec: Optional[str] = None) -> Tuple[LLMProvider, str]:
        spec = (model_spec or settings.default_model or "").strip()
        s_lower = spec.lower()

        # Explicit provider prefixes
        if s_lower.startswith("ollama/"):
            return self.ollama, spec[len("ollama/"):]
        if s_lower.startswith("gemini/"):
            return self.gemini, spec[len("gemini/"):]
        if s_lower.startswith("groq/"):
            return self.groq, spec[len("groq/"):]
        if s_lower.startswith("teja/"):
            return self.teja, spec[len("teja/"):]

        # Auto-detection
        if "teja" in s_lower or "colab" in s_lower or (settings.teja_model_url and "gemma" in s_lower):
            return self.teja, spec

        if s_lower.startswith("qwen/qwen3") or "gpt-oss" in s_lower:
            return self.groq, spec

        if "qwen" in s_lower or "deepseek" in s_lower or "mistral" in s_lower or "llama" in s_lower:
            # Check if Ollama is running or if user prefers Ollama
            h = self.ollama.health()
            if h.get("connected") or settings.provider == "ollama":
                return self.ollama, spec

        if "groq" in s_lower or (settings.groq_api_key and not settings.gemini_api_key and settings.provider != "ollama"):
            return self.groq, spec

        if "gemini" in s_lower or settings.gemini_api_key:
            return self.gemini, spec

        if settings.groq_api_key:
            return self.groq, spec

        # Default to Ollama provider
        return self.ollama, spec

    def list_all_models(self) -> Dict[str, Any]:
        """Aggregate all available models across providers with status."""
        ollama_health = self.ollama.health()
        ollama_models = self.ollama.list_models() if ollama_health.get("connected") else []

        gemini_health = self.gemini.health()
        gemini_models = self.gemini.list_models() if gemini_health.get("connected") else []

        groq_health = self.groq.health()
        groq_models = self.groq.list_models() if groq_health.get("connected") else []

        teja_health = self.teja.health()
        teja_models = self.teja.list_models() if teja_health.get("connected") else []

        return {
            "providers": {
                "ollama": ollama_health,
                "gemini": gemini_health,
                "groq": groq_health,
                "teja": teja_health,
            },
            "models": {
                "ollama": ollama_models,
                "gemini": gemini_models,
                "groq": groq_models,
                "teja": teja_models,
            }
        }


class LLMClient:
    """Backward-compatible LLMClient that wraps LLMRouter."""

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.default_model
        self.router = LLMRouter()

    def complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.1,
    ) -> LLMResponse:
        provider, model_id = self.router.get_provider_and_model(self.model_name)
        try:
            return provider.complete(messages, tools=tools, temperature=temperature, model=model_id)
        except Exception as exc:
            err_str = str(exc).lower()
            # If Gemini fails with quota 429, failover to Groq if key exists
            if ("429" in err_str or "quota" in err_str or "resourceexhausted" in err_str) and settings.groq_api_key:
                return self.router.groq.complete(messages, tools=tools, temperature=temperature)
            raise
