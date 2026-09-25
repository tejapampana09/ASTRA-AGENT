from __future__ import annotations

import time
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.observability.metrics import calculate_cost, metrics_collector
from app.observability.tracing import tracer


@pytest.fixture
def client():
    return TestClient(app)


def test_p4_6_opentelemetry_tracing_and_spans():
    """
    P4.6 TEST:
    Proves OpenTelemetryTracer captures execution spans, computes durations,
    and organizes spans by task_id.
    """
    task_id = "test-task-trace-01"
    tracer.clear(task_id)

    with tracer.span("astra.task.run", task_id=task_id, attributes={"env": "test"}) as outer:
        time.sleep(0.02)
        with tracer.span("astra.node.plan", task_id=task_id, attributes={"steps": 3}) as inner:
            time.sleep(0.01)

    spans = tracer.get_task_spans(task_id)
    assert len(spans) == 2

    # Check span structure
    run_span = next(s for s in spans if s["name"] == "astra.task.run")
    assert run_span["task_id"] == task_id
    assert run_span["duration_ms"] >= 20.0
    assert run_span["attributes"]["env"] == "test"
    assert run_span["status"] == "OK"

    plan_span = next(s for s in spans if s["name"] == "astra.node.plan")
    assert plan_span["attributes"]["steps"] == 3
    assert plan_span["duration_ms"] >= 10.0


def test_p4_6_token_tracking_and_cost_estimation():
    """
    P4.6 TEST:
    Proves token counting, model pricing rates, and task cost estimation.
    """
    # 1. Test calculation logic directly
    # Claude 3.5 Sonnet: $3.00 / 1M prompt, $15.00 / 1M completion
    cost_claude = calculate_cost(prompt_tokens=1_000_000, completion_tokens=1_000_000, model="claude-sonnet")
    assert cost_claude == 18.0

    # GPT-4o-mini: $0.15 / 1M prompt, $0.60 / 1M completion
    cost_gpt_mini = calculate_cost(prompt_tokens=1_000_000, completion_tokens=1_000_000, model="gpt-4o-mini")
    assert cost_gpt_mini == 0.75

    # 2. Test TaskMetrics recording
    task_id = "test-task-tokens-01"
    m = metrics_collector.get_or_create(task_id)
    m.record_tokens(prompt_tokens=5000, completion_tokens=1000, model="claude-sonnet")

    assert m.prompt_tokens == 5000
    assert m.completion_tokens == 1000
    assert m.total_tokens == 6000
    assert m.estimated_cost_usd > 0.0


def test_p4_6_tool_latencies_and_failure_metrics():
    """
    P4.6 TEST:
    Proves tool execution latency tracking, average computation,
    and failure categorization aggregation.
    """
    task_id = "test-task-tools-01"
    m = metrics_collector.get_or_create(task_id)

    # Record tool calls
    m.record_tool_call("file_editor", 150.0)
    m.record_tool_call("file_editor", 250.0)
    m.record_tool_call("pytest_runner", 500.0)

    # Record failures and verification
    m.record_failure("runtime_error")
    m.record_failure("runtime_error")
    m.record_failure("syntax_error")
    m.record_verification("verified")

    data = m.to_dict()
    assert data["tool_call_count"] == 3
    assert data["tool_metrics"]["file_editor"]["avg_ms"] == 200.0
    assert data["tool_metrics"]["pytest_runner"]["avg_ms"] == 500.0
    assert data["failure_categories"]["runtime_error"] == 2
    assert data["failure_categories"]["syntax_error"] == 1
    assert data["is_verified"] is True


def test_p4_6_metrics_api_endpoints(client):
    """
    P4.6 TEST:
    Proves GET /api/metrics and GET /api/metrics/{task_id} expose
    live operational observability and telemetry data.
    """
    task_id = "test-task-api-metrics-01"
    m = metrics_collector.get_or_create(task_id)
    m.record_tokens(1000, 500, model="claude-sonnet")
    m.record_tool_call("terminal", 80.0)
    m.record_verification("verified")

    with tracer.span("astra.api.test", task_id=task_id):
        pass

    # 1. Global Metrics
    global_resp = client.get("/api/metrics")
    assert global_resp.status_code == 200
    global_data = global_resp.json()
    assert global_data["total_tasks"] >= 1
    assert "verification_pass_rate_pct" in global_data
    assert "tool_usage_summary" in global_data

    # 2. Task Metrics
    task_resp = client.get(f"/api/metrics/{task_id}")
    assert task_resp.status_code == 200
    task_data = task_resp.json()
    assert task_data["task_id"] == task_id
    assert task_data["total_tokens"] == 1500
    assert len(task_data["trace_spans"]) >= 1
