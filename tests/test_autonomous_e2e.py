"""End-to-End Test for ASTRA V4 Autonomous Loop (Section 41 Required E2E Test).

Scenario:
1. Creates an intentionally broken sample project:
   def add(a, b):
       return a - b
   assert add(2, 3) == 5
2. Pytest initially fails.
3. ASTRA executes autonomous loop:
   Reads code -> Identifies bug -> Performs surgical edit -> Verifies with pytest -> Passes!
"""
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
import pytest

from astra.agent import AstraAgent
from astra.llm import LLMResponse
from astra.verifier import IndependentVerifier


@pytest.fixture
def broken_sample_project():
    td = tempfile.mkdtemp()
    ws = Path(td).resolve()

    # Broken implementation
    calc_file = ws / "calculator.py"
    calc_file.write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")

    # Failing test
    tests_dir = ws / "tests"
    tests_dir.mkdir()
    test_file = tests_dir / "test_calculator.py"
    test_file.write_text("from calculator import add\n\ndef test_add():\n    assert add(2, 3) == 5\n", encoding="utf-8")

    yield ws
    shutil.rmtree(td, ignore_errors=True)


def test_initial_broken_project_fails(broken_sample_project):
    """Confirm the test in broken project fails as expected before ASTRA intervention."""
    res = subprocess.run(
        ["python", "-m", "pytest", "-q"],
        cwd=broken_sample_project,
        capture_output=True,
        text=True,
    )
    assert res.returncode != 0
    assert "FAILED" in (res.stdout + res.stderr)


class DeterministicAutonomousLLM:
    """Simulates realistic LLM responses across autonomous turns to test full agent orchestration deterministically."""

    def __init__(self):
        self.step = 0

    def complete(self, messages: List[Dict[str, Any]], tools=None, temperature=0.1, model=None) -> LLMResponse:
        self.step += 1
        
        # Step 1: LLM decides to explore repository and read the failing calculator.py
        if self.step == 1:
            return LLMResponse(
                content="I will inspect the implementation in calculator.py to diagnose why the test fails.",
                tool_calls=[{
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "read_file", "arguments": {"file_path": "calculator.py"}},
                }],
            )

        # Step 2: LLM identifies the bug (returns a - b instead of a + b) and performs surgical edit
        if self.step == 2:
            return LLMResponse(
                content="The function subtracts instead of adding. I will edit calculator.py to return a + b.",
                tool_calls=[{
                    "id": "call_2",
                    "type": "function",
                    "function": {
                        "name": "edit_file",
                        "arguments": {
                            "file_path": "calculator.py",
                            "target_snippet": "return a - b",
                            "replacement_snippet": "return a + b",
                        },
                    },
                }],
            )

        # Step 3: LLM says it has completed the work
        return LLMResponse(
            content="I have updated calculator.py to correctly add numbers. All tests should now pass.",
            tool_calls=[],
        )


def test_autonomous_fix_and_verification_e2e(broken_sample_project, monkeypatch):
    """Run ASTRA autonomous agent through the required Section 41 workflow."""
    agent = AstraAgent(workspace_path=broken_sample_project, max_iterations=10)

    # Inject deterministic LLM to test agent autonomous loop without depending on external network quota
    fake_llm = DeterministicAutonomousLLM()
    monkeypatch.setattr(agent.llm, "complete", fake_llm.complete)

    # Run the autonomous goal
    result = agent.run("Fix the failing test in calculator.py")

    # Verify agent reported success
    assert result["status"] == "completed"
    assert "calculator.py" in result["files_modified"]
    assert result["verification"] == "passed"

    # Verify file was actually fixed on disk
    updated_code = (broken_sample_project / "calculator.py").read_text(encoding="utf-8")
    assert "return a + b" in updated_code

    # Independently verify pytest succeeds on disk
    verifier = IndependentVerifier(broken_sample_project)
    v_res = verifier.verify(["calculator.py"])
    assert v_res.passed is True
    assert v_res.phase == "verified"
