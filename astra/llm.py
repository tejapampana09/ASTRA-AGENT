"""Unified LLM provider interface for ASTRA with real tool-calling across all backends.

Supports:
1. TejaAI GPU Server (Fine-Tuned Gemma with native structured tool-calling & parsing)
2. Groq (High-throughput Llama 3.3 70B with 14,400 free requests/day & native tools)
3. Google Gemini (Gemini 3.5 Flash / Flash-Lite / Pro with native function calling)
4. OpenRouter / OpenAI / Claude / LiteLLM / Ollama
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple
from astra.config import settings


class LLMResponse:
    """Standardized response from any LLM provider."""

    def __init__(
        self,
        content: str = "",
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        raw_content: Any = None,
    ):
        self.content = content
        self.tool_calls = tool_calls or []
        self.raw_content = raw_content

    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0

    def __repr__(self) -> str:
        return f"<LLMResponse tools={len(self.tool_calls)} content_len={len(self.content)}>"


def check_endpoint_health(url: str, timeout: int = 4) -> bool:
    """Fast check to ensure custom endpoint or server is actually online."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ASTRA/3.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status < 500
    except Exception:
        return False


def parse_gemma_tool_calls(text: str) -> Tuple[str, List[Dict[str, Any]]]:
    """Parse tool calls from Gemma model output.
    
    Supports:
    - `<|tool_call>call:func_name{args}<tool_call|>`
    - ````json {"name": "func", "arguments": {...}} ````
    - Raw JSON `{"name": "...", "arguments": {...}}` or `{"tool": "...", "args": {...}}`
    """
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
            "id": f"call_teja_{fn_name}",
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
                tool_calls.append({
                    "id": f"call_teja_{fn_name}",
                    "type": "function",
                    "function": {"name": fn_name, "arguments": fn_args},
                })
        except Exception:
            pass

    if tool_calls:
        cleaned_text = json_block_pattern.sub("", text).strip()
        return cleaned_text, tool_calls

    # Pattern 3: Standalone JSON object with "name" and "arguments"
    raw_obj_pattern = re.compile(r'(\{\s*"(?:name|tool)"\s*:\s*"[^"]+".*?\})', re.DOTALL)
    for match in raw_obj_pattern.finditer(text):
        raw_json = match.group(1).strip()
        try:
            data = json.loads(raw_json)
            fn_name = data.get("name") or data.get("tool")
            if fn_name and isinstance(fn_name, str):
                fn_args = data.get("arguments") or data.get("args") or {}
                tool_calls.append({
                    "id": f"call_teja_{fn_name}",
                    "type": "function",
                    "function": {"name": fn_name, "arguments": fn_args},
                })
        except Exception:
            pass

    if tool_calls:
        cleaned_text = raw_obj_pattern.sub("", text).strip()
        return cleaned_text, tool_calls

    return text.strip(), []


class LLMClient:
    """Unified client for routing completions across model backends with native tool-calling."""

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.default_model

    def complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.1,
    ) -> LLMResponse:
        """Synchronous chat completion with automatic provider dispatch and quota protection."""
        model = (self.model_name or "").lower()

        # 1. Custom TejaAI Model Server (Colab/Kaggle GPU)
        if "teja" in model or "colab" in model or (settings.teja_model_url and "gemma" in model):
            return self._call_teja_gpu_server(messages, tools, temperature)

        # 2. Groq (High throughput, 14,400 free requests/day)
        if "groq" in model or "llama" in model or (settings.groq_api_key and not settings.gemini_api_key):
            return self._call_groq(messages, tools, temperature)

        # 3. OpenRouter
        if "openrouter" in model or (settings.openrouter_api_key and not settings.gemini_api_key):
            return self._call_openrouter(messages, tools, temperature)

        # 4. Google Gemini API with automatic Groq fallback on quota exhaustion
        if "gemini" in model or settings.gemini_api_key:
            try:
                return self._call_gemini(messages, tools, temperature)
            except Exception as exc:
                err_str = str(exc).lower()
                if ("429" in err_str or "quota" in err_str or "resourceexhausted" in err_str) and settings.groq_api_key:
                    # Automatic quota failover to Groq
                    return self._call_groq(messages, tools, temperature)
                raise

        # 5. Fallback to LiteLLM (OpenAI, Claude, Ollama)
        return self._call_litellm(messages, tools, temperature)

    def _call_teja_gpu_server(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.1,
    ) -> LLMResponse:
        """Call TejaAI GPU endpoint with full tool-calling schema and response parsing."""
        url = settings.teja_model_url.strip()
        if not url:
            raise ValueError(
                "TEJA_MODEL_URL is not set in .env. Please configure your Cloudflare URL or switch model: /model gemini"
            )

        # Root health check
        base_url = url.replace("/v1", "").rstrip("/")
        if not check_endpoint_health(f"{base_url}/health", timeout=4):
            raise ConnectionError(
                f"TejaAI GPU server is offline or unreachable at '{url}'.\n"
                "Please verify your Kaggle/Colab notebook & Cloudflare tunnel are running, or switch model: /model gemini"
            )

        # Format tool descriptions if tools are available
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

        # Build clean message history tailored for Gemma 4
        clean_messages = []
        for idx, m in enumerate(messages):
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
                raw_text = choice.get("message", {}).get("content", "").strip()

                # Parse tool calls from model output
                thought, tool_calls = parse_gemma_tool_calls(raw_text)
                return LLMResponse(content=thought or raw_text, tool_calls=tool_calls)

        except urllib.error.HTTPError as http_err:
            try:
                err_body = http_err.read().decode("utf-8")
                detail = json.loads(err_body).get("detail", err_body)
            except Exception:
                detail = str(http_err)
            raise RuntimeError(f"TejaAI GPU Server Error ({http_err.code}): {detail}")
        except Exception as exc:
            raise RuntimeError(f"Failed to communicate with TejaAI GPU server: {exc}")

    def _call_groq(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.1,
    ) -> LLMResponse:
        """Call Groq API directly with native function calling and high throughput."""
        api_key = settings.groq_api_key or os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY is not set in .env. Get your free key with 14,400 req/day at https://console.groq.com"
            )

        model_id = "openai/gpt-oss-120b"
        m_lower = (self.model_name or "").lower()
        if "20b" in m_lower or "fast" in m_lower:
            model_id = "openai/gpt-oss-20b"
        elif "qwen" in m_lower:
            model_id = "qwen/qwen3.8-27b"
        elif m_lower and m_lower not in ("groq", "default"):
            model_id = self.model_name

        # Format messages for OpenAI standard
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
            "max_tokens": 2048,
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
                "User-Agent": "ASTRA/3.0",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
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

                return LLMResponse(content=content, tool_calls=tool_calls)
        except urllib.error.HTTPError as http_err:
            try:
                err_detail = http_err.read().decode("utf-8")
            except Exception:
                err_detail = str(http_err)
            raise RuntimeError(f"Groq API Error ({http_err.code}): {err_detail}")
        except Exception as exc:
            raise RuntimeError(f"Groq API communication error: {exc}")

    def _call_openrouter(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.1,
    ) -> LLMResponse:
        """Call OpenRouter with standard OpenAI function calling."""
        api_key = settings.openrouter_api_key or os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is not set in .env.")

        model_id = self.model_name
        if model_id == "openrouter" or "openrouter/" not in model_id:
            model_id = "google/gemini-2.0-flash-exp:free"

        payload: Dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = [{"type": "function", "function": t} for t in tools]

        url = "https://openrouter.ai/api/v1/chat/completions"
        req_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=req_data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://github.com/tejapampana09/ASTRA-AGENT",
                "X-Title": "ASTRA Agent",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                choice = data.get("choices", [{}])[0]
                message = choice.get("message", {})
                content = message.get("content") or ""
                tool_calls = message.get("tool_calls") or []
                return LLMResponse(content=content, tool_calls=tool_calls)
        except Exception as exc:
            raise RuntimeError(f"OpenRouter API error: {exc}")

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
                "or configure GROQ_API_KEY for free high-quota access."
            )

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)

            model_id = "gemini-3.5-flash-lite"
            if "flash" in self.model_name and "lite" not in self.model_name and "3.8" not in self.model_name:
                model_id = "gemini-3.5-flash"
            elif "3.8" in self.model_name:
                model_id = "gemini-3.8-flash"
            elif "pro" in self.model_name:
                model_id = "gemini-3.5-pro"
            elif self.model_name and "gemini" in self.model_name:
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
