"""ASTRA V4 Configuration and Environment Management."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load local .env
load_dotenv(override=True)


class Config:
    def __init__(self, workspace_path: Optional[str] = None):
        self.workspace_path = Path(workspace_path or os.getenv("ASTRA_WORKSPACE") or os.getcwd()).resolve()
        
        # Provider & Model Settings
        self.provider = os.getenv("ASTRA_PROVIDER") or "ollama"
        self.default_model = os.getenv("ASTRA_MODEL") or os.getenv("LLM_MODEL") or "qwen2.5-coder:7b"
        self.ollama_base_url = (os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/")
        
        # Keys & Remote Endpoints
        self.gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
        self.groq_api_key = os.getenv("GROQ_API_KEY") or ""
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY") or ""
        self.openai_api_key = os.getenv("OPENAI_API_KEY") or ""
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY") or ""
        self.teja_model_url = os.getenv("TEJA_MODEL_URL") or ""
        self.hf_token = os.getenv("HF_TOKEN") or ""
        self.teja_hf_model = os.getenv("TEJA_HF_MODEL") or ""
        
        # Execution & Security Controls
        self.max_iterations = int(os.getenv("ASTRA_MAX_ITERATIONS", "30"))
        self.command_timeout = int(os.getenv("ASTRA_COMMAND_TIMEOUT", "120"))
        self.permission_mode = os.getenv("ASTRA_PERMISSION_MODE", "balanced").lower() # safe, balanced, strict
        self.timeout_seconds = int(os.getenv("ASTRA_TIMEOUT", "300"))
        
        # API Server & Security
        self.api_host = os.getenv("ASTRA_HOST", "127.0.0.1")
        self.api_port = int(os.getenv("ASTRA_PORT", "8765"))
        self.api_token = os.getenv("ASTRA_API_TOKEN") or ""
        raw_origins = [
            o.strip() for o in (
                os.getenv("ASTRA_ALLOWED_ORIGINS") or
                "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8765,http://127.0.0.1:8765,app://-"
            ).split(",") if o.strip()
        ]
        # Never allow wildcard '*' when credentials or sensitive operations are enabled
        self.allowed_origins = [o for o in raw_origins if o != "*"]
        if not self.allowed_origins:
            self.allowed_origins = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8765", "http://127.0.0.1:8765", "app://-"]

        self.allowed_workspaces = [
            Path(p.strip()).resolve() for p in os.getenv("ASTRA_ALLOWED_WORKSPACES", "").split(",") if p.strip()
        ]
        self.max_output_chars = int(os.getenv("ASTRA_MAX_OUTPUT_CHARS", "65536"))
        self.circuit_breaker_enabled = os.getenv("ASTRA_CIRCUIT_BREAKER", "true").lower() in ("1", "true", "yes")

        # Data directory for sessions & persistence
        self.data_dir = Path(os.getenv("ASTRA_DATA_DIR") or Path.home() / ".astra").resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "astra_v4.db"

    def reload(self) -> None:
        load_dotenv(override=True)
        self.provider = os.getenv("ASTRA_PROVIDER") or self.provider
        self.gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
        self.groq_api_key = os.getenv("GROQ_API_KEY") or ""
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY") or ""
        self.openai_api_key = os.getenv("OPENAI_API_KEY") or ""
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY") or ""
        self.ollama_base_url = (os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/")
        self.teja_model_url = os.getenv("TEJA_MODEL_URL") or ""
        self.default_model = os.getenv("ASTRA_MODEL") or os.getenv("LLM_MODEL") or self.default_model
        self.max_iterations = int(os.getenv("ASTRA_MAX_ITERATIONS", str(self.max_iterations)))
        self.command_timeout = int(os.getenv("ASTRA_COMMAND_TIMEOUT", str(self.command_timeout)))
        self.permission_mode = os.getenv("ASTRA_PERMISSION_MODE", self.permission_mode).lower()
        self.timeout_seconds = int(os.getenv("ASTRA_TIMEOUT", str(self.timeout_seconds)))
        self.api_token = os.getenv("ASTRA_API_TOKEN") or ""
        raw_origins = [
            o.strip() for o in (
                os.getenv("ASTRA_ALLOWED_ORIGINS") or
                "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8765,http://127.0.0.1:8765,app://-"
            ).split(",") if o.strip()
        ]
        self.allowed_origins = [o for o in raw_origins if o != "*"]
        if not self.allowed_origins:
            self.allowed_origins = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8765", "http://127.0.0.1:8765", "app://-"]

        self.allowed_workspaces = [
            Path(p.strip()).resolve() for p in os.getenv("ASTRA_ALLOWED_WORKSPACES", "").split(",") if p.strip()
        ]
        self.max_output_chars = int(os.getenv("ASTRA_MAX_OUTPUT_CHARS", "65536"))
        self.circuit_breaker_enabled = os.getenv("ASTRA_CIRCUIT_BREAKER", "true").lower() in ("1", "true", "yes")


settings = Config()
