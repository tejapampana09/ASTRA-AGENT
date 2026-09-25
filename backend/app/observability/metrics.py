from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class TaskMetrics:
    task_id: str
    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    tool_call_count: int = 0
    iteration_count: int = 0
    retry_count: int = 0

    @property
    def latency_seconds(self) -> float:
        end = self.end_time or time.time()
        return round(end - self.start_time, 2)

    def finalize(self):
        self.end_time = time.time()

    def to_dict(self) -> Dict[str, object]:
        return {
            "task_id": self.task_id,
            "latency_seconds": self.latency_seconds,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": self.total_cost_usd,
            "tool_call_count": self.tool_call_count,
            "iteration_count": self.iteration_count,
            "retry_count": self.retry_count,
        }


class MetricsCollector:
    """Collects and aggregates performance, cost, and reliability metrics across task executions."""

    def __init__(self):
        self._metrics: Dict[str, TaskMetrics] = {}

    def get_or_create(self, task_id: str) -> TaskMetrics:
        if task_id not in self._metrics:
            self._metrics[task_id] = TaskMetrics(task_id=task_id)
        return self._metrics[task_id]


metrics_collector = MetricsCollector()
