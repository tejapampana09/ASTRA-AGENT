from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Dict, Optional

from app.config import settings
from app.observability.logging import logger


class OpenTelemetryTracer:
    """Provides OpenTelemetry and LangSmith tracing hooks for task runs and tool execution."""

    def __init__(self):
        self.enabled = bool(settings.OTEL_EXPORTER_OTLP_ENDPOINT or settings.LANGCHAIN_TRACING_V2)
        if settings.LANGCHAIN_TRACING_V2 and settings.LANGCHAIN_API_KEY:
            os.environ["LANGCHAIN_TRACING_V2"] = "true"
            os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
            os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT

    @contextmanager
    def span(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        logger.debug(f"[TraceSpan:Start] {name} - attrs: {attributes}")
        try:
            yield
        finally:
            logger.debug(f"[TraceSpan:End] {name}")


tracer = OpenTelemetryTracer()
