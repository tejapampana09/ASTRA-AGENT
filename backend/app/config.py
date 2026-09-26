from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


from dotenv import load_dotenv

# Ensure environment variables are loaded into os.environ
load_dotenv(".env")
load_dotenv("../.env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Application settings
    APP_NAME: str = "ASTRA 2.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173", "*"]

    # Storage & Persistence
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgrespassword@localhost:5432/astra_db"
    DATABASE_URL_SYNC: str = "postgresql://postgres:postgrespassword@localhost:5432/astra_db"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Embedding & Vector RAG Settings
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSION: int = 1536
    VECTOR_INDEX_TYPE: str = "hnsw"  # hnsw or ivfflat


    # LLM Settings
    LLM_PROVIDER: str = "litellm"
    LLM_MODEL: str = "anthropic/claude-sonnet-4-5-20250929"
    LLM_API_KEY: Optional[str] = None
    LLM_BASE_URL: Optional[str] = None
    LLM_TEMPERATURE: float = 0.1
    LLM_TIMEOUT_SECONDS: int = 120

    # Router Profile Models
    ROUTER_FAST_MODEL: str = "openai/gpt-4o-mini"
    ROUTER_CODING_MODEL: str = "anthropic/claude-sonnet-4-5-20250929"
    ROUTER_REASONING_MODEL: str = "anthropic/claude-sonnet-4-5-20250929"

    # Orchestration & Safeguard Limits
    MAX_ITERATIONS: int = 15
    MAX_TOOL_CALLS: int = 50
    MAX_RUNTIME_SECONDS: int = 1800
    MAX_RETRIES: int = 3

    # Workspace & Sandboxing
    WORKSPACE_BASE_DIR: str = str(Path(__file__).resolve().parent.parent / "workspaces")
    ENABLE_DOCKER_SANDBOX: bool = False
    SANDBOX_CONTAINER_IMAGE: str = "python:3.12-slim"
    COMMAND_TIMEOUT_SECONDS: int = 180

    # GitHub API
    GITHUB_TOKEN: Optional[str] = None
    GITHUB_API_URL: str = "https://api.github.com"

    # OpenHands SDK configuration
    OPENHANDS_SUPPRESS_BANNER: str = "1"

    # Observability
    OTEL_EXPORTER_OTLP_ENDPOINT: Optional[str] = None
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_API_KEY: Optional[str] = None
    LANGCHAIN_PROJECT: str = "astra-2.0"


# Global settings singleton
settings = Settings()

# Ensure OpenHands banner suppression is set in the environment
os.environ["OPENHANDS_SUPPRESS_BANNER"] = settings.OPENHANDS_SUPPRESS_BANNER
