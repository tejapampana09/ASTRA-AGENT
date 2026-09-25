from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


# Pricing rates per 1,000,000 tokens (USD)
MODEL_PRICING = {
    "claude-sonnet": {"prompt": 3.00, "completion": 15.00},
    "claude-3-5-sonnet": {"prompt": 3.00, "completion": 15.00},
    "gpt-4o-mini": {"prompt": 0.15, "completion": 0.60},
    "gpt-4o": {"prompt": 2.50, "completion": 10.00},
    "default": {"prompt": 2.00, "completion": 8.00},
}


def calculate_cost(prompt_tokens: int, completion_tokens: int, model: str = "default") -> float:
    """Calculates estimated LLM cost in USD based on token counts and model rates."""
    matched_rate = MODEL_PRICING.get("default")
    model_lower = model.lower()
    for k, rates in MODEL_PRICING.items():
        if k in model_lower:
            matched_rate = rates
            break

    prompt_cost = (prompt_tokens / 1_000_000.0) * matched_rate["prompt"]
    completion_cost = (completion_tokens / 1_000_000.0) * matched_rate["completion"]
    return round(prompt_cost + completion_cost, 6)


@dataclass
class TaskMetrics:
    task_id: str
    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    tool_call_count: int = 0
    tool_durations_ms: Dict[str, List[float]] = field(default_factory=lambda: defaultdict(list))
    failure_categories: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    verification_status: str = "pending"
    is_verified: bool = False
    iteration_count: int = 0
    retry_count: int = 0

    @property
    def latency_seconds(self) -> float:
        end = self.end_time or time.time()
        return round(end - self.start_time, 2)

    def record_tokens(self, prompt_tokens: int, completion_tokens: int, model: str = "default") -> None:
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens
        self.total_tokens = self.prompt_tokens + self.completion_tokens
        self.estimated_cost_usd = round(
            self.estimated_cost_usd + calculate_cost(prompt_tokens, completion_tokens, model),
            6,
        )

    def record_tool_call(self, tool_name: str, duration_ms: float) -> None:
        self.tool_call_count += 1
        self.tool_durations_ms[tool_name].append(duration_ms)

    def record_failure(self, category: str) -> None:
        cat_key = category.lower().strip() or "general"
        self.failure_categories[cat_key] += 1

    def record_verification(self, status: str) -> None:
        self.verification_status = status.lower()
        self.is_verified = self.verification_status in ["verified", "partially_verified"]

    def finalize(self) -> None:
        if not self.end_time:
            self.end_time = time.time()

    def to_dict(self) -> Dict[str, Any]:
        tool_averages = {
            t: {
                "count": len(durs),
                "total_ms": round(sum(durs), 2),
                "avg_ms": round(sum(durs) / len(durs), 2) if durs else 0.0,
            }
            for t, durs in self.tool_durations_ms.items()
        }
        return {
            "task_id": self.task_id,
            "latency_seconds": self.latency_seconds,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "tool_call_count": self.tool_call_count,
            "tool_metrics": tool_averages,
            "failure_categories": dict(self.failure_categories),
            "verification_status": self.verification_status,
            "is_verified": self.is_verified,
            "iteration_count": self.iteration_count,
            "retry_count": self.retry_count,
        }


class MetricsCollector:
    """
    Production-grade metrics and cost aggregation engine for ASTRA 2.0 (Phase 4.6).
    Tracks live tokens, costs, tool execution latencies, failure distributions,
    and verification pass rates across the autonomous platform.
    """

    def __init__(self):
        self._metrics: Dict[str, TaskMetrics] = {}

    def get_or_create(self, task_id: str) -> TaskMetrics:
        if task_id not in self._metrics:
            self._metrics[task_id] = TaskMetrics(task_id=task_id)
        return self._metrics[task_id]

    def get_aggregate_summary(self) -> Dict[str, Any]:
        """Computes platform-wide reliability, cost, and latency analytics."""
        all_metrics = list(self._metrics.values())
        total_tasks = len(all_metrics)
        if total_tasks == 0:
            return {
                "total_tasks": 0,
                "verified_tasks": 0,
                "verification_pass_rate_pct": 0.0,
                "total_tokens_consumed": 0,
                "total_estimated_cost_usd": 0.0,
                "average_latency_seconds": 0.0,
                "tool_usage_summary": {},
                "failure_distribution": {},
            }

        verified_count = sum(1 for m in all_metrics if m.is_verified)
        pass_rate = round((verified_count / total_tasks) * 100, 2)
        total_tokens = sum(m.total_tokens for m in all_metrics)
        total_cost = round(sum(m.estimated_cost_usd for m in all_metrics), 4)
        avg_latency = round(sum(m.latency_seconds for m in all_metrics) / total_tasks, 2)

        # Aggregate tool usage
        tool_agg: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"count": 0, "total_ms": 0.0})
        for m in all_metrics:
            for t_name, durs in m.tool_durations_ms.items():
                tool_agg[t_name]["count"] += len(durs)
                tool_agg[t_name]["total_ms"] += sum(durs)

        for t_name, data in tool_agg.items():
            count = data["count"]
            data["avg_ms"] = round(data["total_ms"] / count, 2) if count else 0.0
            data["total_ms"] = round(data["total_ms"], 2)

        # Aggregate failure categories
        fail_agg: Dict[str, int] = defaultdict(int)
        for m in all_metrics:
            for cat, cnt in m.failure_categories.items():
                fail_agg[cat] += cnt

        return {
            "total_tasks": total_tasks,
            "verified_tasks": verified_count,
            "verification_pass_rate_pct": pass_rate,
            "total_tokens_consumed": total_tokens,
            "total_estimated_cost_usd": total_cost,
            "average_latency_seconds": avg_latency,
            "tool_usage_summary": dict(tool_agg),
            "failure_distribution": dict(fail_agg),
        }

    def clear(self):
        self._metrics.clear()


# Global metrics collector singleton
metrics_collector = MetricsCollector()
