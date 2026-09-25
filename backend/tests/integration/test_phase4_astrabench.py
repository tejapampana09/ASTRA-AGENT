from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.evaluation.bench import ASTRA_BENCHMARK_TASKS, astra_bench
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_p4_7_astrabench_suite_execution():
    """
    P4.7 TEST:
    Executes the full ASTRA-Bench self-evaluation benchmark suite across
    all 5 core engineering categories: bug_fix, refactoring, feature_addition,
    multi_file, and import_fix.
    """
    suite_result = astra_bench.run_suite()

    assert suite_result.total_tasks == 5
    assert suite_result.passed_tasks == 5
    assert suite_result.resolution_rate_pct == 100.0
    assert suite_result.average_evidence_score == 1.0
    assert suite_result.average_duration_seconds > 0.0

    # Verify every category is represented
    expected_categories = {"bug_fix", "refactoring", "feature_addition", "multi_file", "import_fix"}
    actual_categories = set(suite_result.category_summary.keys())
    assert expected_categories.issubset(actual_categories)

    for cat, stats in suite_result.category_summary.items():
        assert stats["total"] >= 1
        assert stats["passed"] == stats["total"]
        assert stats["pass_rate_pct"] == 100.0


def test_p4_7_astrabench_category_filtering():
    """
    P4.7 TEST:
    Proves category filtering executes only targeted benchmarks.
    """
    result = astra_bench.run_suite(category="bug_fix")
    assert result.total_tasks == 1
    assert result.results[0].category == "bug_fix"
    assert result.results[0].passed is True
    assert result.resolution_rate_pct == 100.0


def test_p4_7_astrabench_api_endpoints(client):
    """
    P4.7 TEST:
    Proves GET /api/benchmarks and POST /api/benchmarks/run expose
    evaluation specs and return objective benchmark scorecards.
    """
    # 1. List benchmarks
    list_resp = client.get("/api/benchmarks")
    assert list_resp.status_code == 200
    tasks = list_resp.json()
    assert len(tasks) == 5
    assert tasks[0]["task_id"] == "bench-01-bugfix"

    # 2. Run single category via API
    run_resp = client.post("/api/benchmarks/run", json={"category": "feature_addition"})
    assert run_resp.status_code == 200
    scorecard = run_resp.json()
    assert scorecard["total_tasks"] == 1
    assert scorecard["passed_tasks"] == 1
    assert scorecard["resolution_rate_pct"] == 100.0
