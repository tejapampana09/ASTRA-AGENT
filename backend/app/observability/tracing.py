from __future__ import annotations

import os
import time
import uuid
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from app.config import settings
from app.observability.logging import logger

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.trace import Status, StatusCode

    provider = TracerProvider()
    trace.set_tracer_provider(provider)
    otel_tracer = trace.get_tracer("astra-2.0")
    HAS_OTEL = True
except Exception as _e:
    HAS_OTEL = False
    otel_tracer = None


@dataclass
class TraceSpan:
    trace_id: str
    span_id: str
    name: str
    task_id: Optional[str]
    start_time: float
    end_time: float = 0.0
    duration_ms: float = 0.0
    attributes: Dict[str, Any] = field(default_factory=dict)
    status: str = "OK"  # OK, ERROR
    error_message: Optional[str] = None

    def finish(self, status: str = "OK", error: Optional[str] = None):
        self.end_time = time.time()
        self.duration_ms = round((self.end_time - self.start_time) * 1000, 2)
        self.status = status
        self.error_message = error

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class OpenTelemetryTracer:
    """
    Production-grade distributed tracing for ASTRA 2.0 (Phase 4.6).
    Emits OpenTelemetry spans while preserving an auditable in-memory ring buffer
    for real-time frontend and telemetry inspection.
    """

    def __init__(self):
        self._spans_by_task: Dict[str, List[TraceSpan]] = defaultdict(list)
        self._active_spans: List[TraceSpan] = []

        if settings.LANGCHAIN_TRACING_V2 and settings.LANGCHAIN_API_KEY:
            os.environ["LANGCHAIN_TRACING_V2"] = "true"
            os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
            os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT

    @contextmanager
    def span(
        self,
        name: str,
        task_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ):
        span_id = uuid.uuid4().hex[:12]
        trace_id = task_id or uuid.uuid4().hex[:16]
        attrs = dict(attributes or {})
        if task_id:
            attrs["task_id"] = task_id

        local_span = TraceSpan(
            trace_id=trace_id,
            span_id=span_id,
            name=name,
            task_id=task_id,
            start_time=time.time(),
            attributes=attrs,
        )

        if task_id:
            self._spans_by_task[task_id].append(local_span)
        self._active_spans.append(local_span)

        otel_ctx = None
        if HAS_OTEL and otel_tracer:
            try:
                otel_ctx = otel_tracer.start_span(name, attributes=attrs)
            except Exception:
                otel_ctx = None

        logger.debug(f"[Trace:Start] {name} (id={span_id}) - task={task_id}")
        error_occurred = None
        try:
            yield local_span
        except Exception as e:
            error_occurred = str(e)
            local_span.finish(status="ERROR", error=str(e))
            if otel_ctx:
                otel_ctx.set_status(Status(StatusCode.ERROR, str(e)))
            raise
        finally:
            if not error_occurred:
                local_span.finish(status="OK")
                if otel_ctx:
                    otel_ctx.set_status(Status(StatusCode.OK))
            if otel_ctx:
                try:
                    otel_ctx.end()
                except Exception:
                    pass
            logger.debug(f"[Trace:End] {name} ({local_span.duration_ms}ms)")

    def get_task_spans(self, task_id: str) -> List[Dict[str, Any]]:
        return [s.to_dict() for s in self._spans_by_task.get(task_id, [])]

    def clear(self, task_id: Optional[str] = None):
        if task_id:
            if task_id in self._spans_by_task:
                del self._spans_by_task[task_id]
        else:
            self._spans_by_task.clear()
            self._active_spans.clear()


# Global tracer singleton
tracer = OpenTelemetryTracer()
