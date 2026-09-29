"""ASTRA Configuration and Environment Management."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load local .env
load_dotenv(override=True)


class Config:
    def __init__(self, workspace_path: Optional[str] = None):
        self.workspace_path = Path(workspace_path or os.getcwd()).resolve()
        self.gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
        self.openai_api_key = os.getenv("OPENAI_API_KEY") or ""
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY") or ""
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434"
        self.teja_model_url = os.getenv("TEJA_MODEL_URL") or ""
        self.default_model = os.getenv("ASTRA_MODEL") or os.getenv("LLM_MODEL") or "gemini-3.5-flash"
        self.timeout_seconds = int(os.getenv("ASTRA_TIMEOUT", "60"))

    def reload(self) -> None:
        load_dotenv(override=True)
        self.gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
        self.openai_api_key = os.getenv("OPENAI_API_KEY") or ""
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY") or ""
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434"
        self.teja_model_url = os.getenv("TEJA_MODEL_URL") or ""
        self.default_model = os.getenv("ASTRA_MODEL") or os.getenv("LLM_MODEL") or "gemini-3.5-flash"


settings = Config()
