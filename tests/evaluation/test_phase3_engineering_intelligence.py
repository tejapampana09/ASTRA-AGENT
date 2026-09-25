from __future__ import annotations

import tempfile
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agents.debugger import AutonomousDebugger, FailureCategory, debug_failure
from app.agents.graph import (
    build_astra_graph,
    finalize_task,
    impact_analysis_node,
    should_continue_or_finalize,
    should_reexecute_or_escalate,
)
from app.agents.planner import plan_task, risk_assessment
from app.agents.replanner import replan_step
from app.agents.verifier import verify_solution
from app.analysis.impact import ChangeImpactAnalyzer
from app.database.models import Base
from app.memory.engineering import EngineeringMemoryStore, set_engineering_memory_store, get_engineering_memory_store
from app.memory.store import TaskMemoryStore, set_task_memory_store
from app.rag.vector_store import InMemoryVectorStore, set_vector_store


@pytest.fixture
def test_db_session():
    """Isolated in-memory SQLite database session factory for Phase 3 tests."""
    engine = create_engine("sqlite:///:memory:", echo=False, future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    yield session_factory
    engine.dispose()


# ==============================================================================
# P3.1: Intelligent Planning & Task Decomposition Benchmark
# ==============================================================================
def test_benchmark_p3_1_intelligent_planning():
    """
    P3.1 MILESTONE:
    Proves that the Intelligent Planner decomposes complex software engineering goals into
    dependency-ordered stages, sets blast-radius safeguards, and defines rollback strategies.
    """
    state = {
        "task_id": "p3-plan-001",
        "repository_id": "auth-service-repo",
        "user_goal": "Add JWT authentication with token revocation and refresh endpoints",
        "repository_context": {
            "summary": {"backend": "FastAPI", "test_command": "pytest"},
            "files": ["services/auth.py", "routes/auth_routes.py", "models/user.py", "tests/test_auth.py"],
            "symbols": ["User", "authenticate", "create_token"],
        },
        "workspace_path": None,
    }

    result = plan_task(state)
    plan = result["plan"]
    plan_metadata = result["plan_metadata"]

    assert len(plan) >= 5, f"Expected multi-stage plan, got {len(plan)} steps"

    # Verify dependency-ordered stages exist
    stages = [step["stage"] for step in plan]
    assert "inspection" in stages
    assert "implementation" in stages
    assert "targeted_verification" in stages
    assert "regression_verification" in stages
    assert "audit_and_report" in stages

    # Verify dependency ordering
    impl_step = next(s for s in plan if s["stage"] == "implementation")
    verify_step = next(s for s in plan if s["stage"] == "targeted_verification")
    assert 1 in impl_step["depends_on"]
    assert impl_step["step"] in verify_step["depends_on"]

    # Verify rollback strategy is attached
    assert "rollback_strategy" in plan_metadata
    assert "git checkout" in plan_metadata["rollback_strategy"]["command"]


# ==============================================================================
# P3.2: Change Impact Analysis Benchmark
# ==============================================================================
def test_benchmark_p3_2_change_impact_analysis():
    """
    P3.2 MILESTONE:
    Proves that ChangeImpactAnalyzer uses AST dependency graphs to identify downstream
    affected files, imported symbols, blast radius score, and relevant test targets.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        ws_path = Path(tmp_dir)

        # 1. Create target service module
        services_dir = ws_path / "services"
        services_dir.mkdir(parents=True, exist_ok=True)
        (services_dir / "auth.py").write_text(
            'def verify_password(plain, hashed):\n    return plain == hashed\n\n'
            'def generate_jwt_token(user_id):\n    return f"token-{user_id}"\n',
            encoding="utf-8"
        )

        # 2. Create downstream route importing auth service
        routes_dir = ws_path / "routes"
        routes_dir.mkdir(parents=True, exist_ok=True)
        (routes_dir / "login.py").write_text(
            'from services.auth import verify_password, generate_jwt_token\n\n'
            'def login_endpoint(user, pwd):\n'
            '    if verify_password(pwd, "secret"):\n'
            '        return generate_jwt_token(user)\n',
            encoding="utf-8"
        )

        # 3. Create independent module
        utils_dir = ws_path / "utils"
        utils_dir.mkdir(parents=True, exist_ok=True)
        (utils_dir / "math_helper.py").write_text(
            'def add(a, b):\n    return a + b\n',
            encoding="utf-8"
        )

        # 4. Create dedicated test file
        tests_dir = ws_path / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / "test_auth.py").write_text(
            'from services.auth import verify_password\n\n'
            'def test_verify():\n    assert verify_password("a", "a")\n',
            encoding="utf-8"
        )

        analyzer = ChangeImpactAnalyzer(ws_path)
        report = analyzer.analyze_impact(target_files=["services/auth.py"])

        assert "routes/login.py" in report.affected_files
        assert "tests/test_auth.py" in report.affected_files or "tests/test_auth.py" in report.relevant_tests
        assert "utils/math_helper.py" not in report.affected_files  # Unaffected isolated file
        assert "verify_password" in report.affected_symbols
        assert "generate_jwt_token" in report.affected_symbols
        assert len(report.relevant_tests) >= 1
        assert report.blast_radius_score > 0.0


# ==============================================================================
# P3.3: Autonomous Debugging & Root Cause Analysis Benchmark
# ==============================================================================
def test_benchmark_p3_3_autonomous_debugging_taxonomy_and_root_cause():
    """
    P3.3 MILESTONE:
    Proves that AutonomousDebugger accurately classifies failures into 7 distinct categories,
    isolates exact code file & line from stack traces, and formulates structured fix hypotheses.
    """
    # 1. Test 7-category taxonomy
    assert AutonomousDebugger.classify_failure("SyntaxError: invalid syntax (auth.py, line 5)") == FailureCategory.SYNTAX
    assert AutonomousDebugger.classify_failure("TypeError: authenticate() missing 1 required positional argument: 'password'") == FailureCategory.TYPE
    assert AutonomousDebugger.classify_failure("ModuleNotFoundError: No module named 'jwt'") == FailureCategory.DEPENDENCY
    assert AutonomousDebugger.classify_failure("AssertionError: assert 401 == 200") == FailureCategory.TEST_ASSERTION
    assert AutonomousDebugger.classify_failure("psycopg2.OperationalError: ConnectionRefused on port 5432") == FailureCategory.INTEGRATION
    assert AutonomousDebugger.classify_failure("PermissionError: [Errno 13] Permission denied: '/var/log/app.log'") == FailureCategory.ENVIRONMENT
    assert AutonomousDebugger.classify_failure("KeyError: 'user_id' not found in payload") == FailureCategory.RUNTIME

    # 2. Test root cause stack trace localization
    sample_traceback = (
        'Traceback (most recent call last):\n'
        '  File "/site-packages/pytest/runner.py", line 150, in pytest_runtest_call\n'
        '    item.runtest()\n'
        '  File "/workspace/tests/test_login.py", line 12, in test_login\n'
        '    response = login_user("alice", "pass")\n'
        '  File "/workspace/services/auth_service.py", line 42, in login_user\n'
        '    return token_builder.sign(payload)\n'
        'TypeError: sign() got an unexpected keyword argument \'algorithm\''
    )

    suspect_file, suspect_line, explanation = AutonomousDebugger.locate_root_cause(sample_traceback)
    assert suspect_file == "/workspace/services/auth_service.py"
    assert suspect_line == 42
    assert "auth_service.py:42" in explanation

    # 3. Test Fix Hypothesis Formulation & Anti-Cycle Learning
    failure_history = []
    hyp1 = AutonomousDebugger.generate_fix_hypothesis(
        category=FailureCategory.TYPE,
        error_msg="TypeError: unexpected keyword",
        suspect_file="services/auth_service.py",
        suspect_line=42,
        failure_history=failure_history
    )
    assert "services/auth_service.py" in hyp1["hypothesis"]
    assert "signature" in hyp1["hypothesis"] or "signature" in hyp1["proposed_fix"]

    # Record first hypothesis in failure history and verify anti-cycle protection triggers on repeat
    failure_history.append({"hypothesis": hyp1["hypothesis"]})
    hyp2 = AutonomousDebugger.generate_fix_hypothesis(
        category=FailureCategory.TYPE,
        error_msg="TypeError: unexpected keyword",
        suspect_file="services/auth_service.py",
        suspect_line=42,
        failure_history=failure_history
    )
    assert "[Alternative Hypothesis]" in hyp2["hypothesis"]


# ==============================================================================
# P3.4: Dynamic Replanning Engine Benchmark
# ==============================================================================
def test_benchmark_p3_4_replanning_engine():
    """
    P3.4 MILESTONE:
    Proves that ReplanningEngine adapts the execution plan specifically to address
    the diagnosed root cause and category instead of blindly repeating the original plan.
    """
    failed_state = {
        "task_id": "task-replan-001",
        "user_goal": "Add JWT authentication",
        "retry_count": 0,
        "files_changed": ["services/auth.py"],
        "failure_history": [
            {
                "category": "test_assertion",
                "suspect_file": "services/auth.py",
                "suspect_line": 35,
                "root_cause": "Failure originated in services/auth.py:35",
                "hypothesis": "Test assertion violated. Token expiration not set.",
                "proposed_fix": "Add 'exp' claim to JWT payload in services/auth.py",
                "error": "AssertionError: 'exp' not in decoded_token",
            }
        ],
        "repository_context": {"summary": {"test_command": "pytest"}},
        "observations": ["Executed initial plan", "Tests failed on assertion"],
    }

    result = replan_step(failed_state)
    assert result["retry_count"] == 1
    new_plan = result["plan"]
    assert len(new_plan) >= 4

    # Verify steps target the diagnosed root cause and file
    assert any("services/auth.py" in s["description"] for s in new_plan)
    assert any("root_cause_inspection" == s["stage"] for s in new_plan)
    assert any("targeted_repair" == s["stage"] for s in new_plan)
    assert any("targeted_verification" == s["stage"] for s in new_plan)
    assert any("regression_verification" == s["stage"] for s in new_plan)


# ==============================================================================
# P3.5: Intelligent Verification & Multi-Factor Evidence Benchmark
# ==============================================================================
def test_benchmark_p3_5_intelligent_verification():
    """
    P3.5 MILESTONE:
    Proves that the Verifier runs targeted tests first, executes regression checks,
    and aggregates empirical multi-factor evidence before certifying a task.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        ws_path = Path(tmp_dir)

        # Write passing test file
        test_file = ws_path / "test_sample.py"
        test_file.write_text("def test_ok(): assert 1 == 1\n", encoding="utf-8")

        state = {
            "task_id": "task-verify-p3",
            "workspace_path": str(ws_path),
            "files_changed": ["test_sample.py"],
            "plan_metadata": {"relevant_tests": ["test_sample.py"]},
            "observations": [],
        }

        res = verify_solution(state)
        assert res["verification_status"] == "verified"

        evidence = res["verification_evidence"]
        assert evidence["status"] == "verified"
        assert evidence["evidence_score"] >= 0.7
        assert evidence["tests"]["passed"] >= 1
        assert evidence["tests"]["failed"] == 0
        assert evidence["diff"]["files_changed_count"] >= 1


# ==============================================================================
# P3.6: Long-Term Engineering Memory Benchmark
# ==============================================================================
def test_benchmark_p3_6_engineering_decision_memory(test_db_session):
    """
    P3.6 MILESTONE:
    Proves that EngineeringMemoryStore captures architectural rules, conventions,
    and proven bug-fix patterns, persisting them to database and injecting them into plans.
    """
    store = EngineeringMemoryStore(db_session_factory=test_db_session)
    set_engineering_memory_store(store)

    # 1. Record an architectural convention
    store.record_decision(
        repo_id="astra-repo",
        category="convention",
        subject="JWT Expiration Standards",
        decision="JWT expiration must be an integer UTC epoch timestamp with minimum 15 minute lifespan.",
        evidence={"standard": "RFC 7519", "approved_by": "lead_architect"}
    )

    # 2. Record a proven bug fix pattern
    store.record_decision(
        repo_id="astra-repo",
        category="proven_fix",
        subject="FastAPI 401 Header Resolution",
        decision="When raising HTTPException(status_code=401), always attach headers={'WWW-Authenticate': 'Bearer'}.",
        evidence={"issue_id": "BUG-882", "verified": True}
    )

    # 3. Retrieve relevant decisions for a related task
    relevant = store.find_relevant_decisions(
        repo_id="astra-repo",
        target_files=["services/auth_service.py"],
        goal="Configure JWT token generation and authentication headers",
        top_k=5
    )

    assert len(relevant) >= 2
    subjects = [r.subject for r in relevant]
    assert "JWT Expiration Standards" in subjects
    assert "FastAPI 401 Header Resolution" in subjects

    # 4. Format for agent prompt
    prompt_text = store.format_decisions_for_prompt(relevant)
    assert "JWT Expiration Standards" in prompt_text
    assert "WWW-Authenticate" in prompt_text


# ==============================================================================
# P3.7: Autonomous Safety & Risk Escalation Benchmark
# ==============================================================================
def test_benchmark_p3_7_autonomous_safety_and_escalation():
    """
    P3.7 MILESTONE:
    Proves that the safety engine classifies actions across the 5-tier risk taxonomy,
    halts on critical hazardous operations, and escalates when retry budget is exhausted.
    """
    # 1. Automatic safe operations (LOW)
    safe_state = {"user_goal": "Refactor auth helper functions", "task_id": "safe-01"}
    safe_res = risk_assessment(safe_state)
    assert safe_res["risk_level"] == "LOW"
    assert not safe_res["approval_required"]

    # 2. Medium risk operations (MEDIUM)
    med_state = {"user_goal": "Run pip install pyjwt and commit changes", "task_id": "med-01"}
    med_res = risk_assessment(med_state)
    assert med_res["risk_level"] == "MEDIUM"

    # 3. High risk operations requiring approval (HIGH)
    high_state = {"user_goal": "git push origin main and create pull request", "task_id": "high-01"}
    high_res = risk_assessment(high_state)
    assert high_res["risk_level"] == "HIGH"
    assert high_res["approval_required"]

    # 4. Critical hazardous operations requiring human authorization (CRITICAL)
    crit_state = {"user_goal": "drop database production_db and format disk", "task_id": "crit-01"}
    crit_res = risk_assessment(crit_state)
    assert crit_res["risk_level"] == "CRITICAL"
    assert crit_res["approval_required"]

    # 5. Escalation routing when retry budget is exhausted
    retry_ok_state = {"retry_count": 2}
    assert should_reexecute_or_escalate(retry_ok_state) == "execute"

    retry_exhausted_state = {"retry_count": 4}  # MAX_RETRIES = 3
    assert should_reexecute_or_escalate(retry_exhausted_state) == "escalate"


# ==============================================================================
# P3.8: Full Autonomous E2E Engineering Intelligence Milestone Gate
# ==============================================================================
def test_benchmark_p3_8_full_autonomous_e2e_lifecycle(test_db_session):
    """
    P3.8 COMPLETION GATE:
    Simulates a complete autonomous engineering mission on an unfamiliar codebase:
    1. Understand & Inspect repository
    2. Change Impact Analysis (identifies affected callers & test files)
    3. Intelligent Multi-Stage Planning (dependency ordered)
    4. Code Execution (simulated defect injection)
    5. Verification (Fails initial test)
    6. Autonomous Debugging & Root Cause Analysis (pinpoints defect location & hypothesis)
    7. Replanning Engine (formulates targeted remediation plan)
    8. Repair & Re-execution
    9. Verification (Passes with empirical evidence)
    10. Finalize & Long-Term Memory Learning (permanently stores proven fix pattern)
    """
    # 1. Setup isolated memory & vector stores
    mem_store = TaskMemoryStore(db_session_factory=test_db_session)
    set_task_memory_store(mem_store)
    eng_store = EngineeringMemoryStore(db_session_factory=test_db_session)
    set_engineering_memory_store(eng_store)
    vec_store = InMemoryVectorStore()
    set_vector_store(vec_store)

    with tempfile.TemporaryDirectory() as tmp_dir:
        ws_path = Path(tmp_dir)

        # Create mini-repo with currency converter
        lib_dir = ws_path / "converter"
        lib_dir.mkdir(parents=True, exist_ok=True)
        calc_file = lib_dir / "calculator.py"
        # Initial code has a deliberate bug: zero division on rate = 0
        calc_file.write_text(
            'def convert_currency(amount: float, rate: float) -> float:\n'
            '    # Defect: missing rate validation\n'
            '    return amount / rate\n',
            encoding="utf-8"
        )

        test_file = ws_path / "test_converter.py"
        test_file.write_text(
            'import pytest\n'
            'from converter.calculator import convert_currency\n\n'
            'def test_convert_valid():\n'
            '    assert convert_currency(100.0, 2.0) == 50.0\n\n'
            'def test_convert_zero_rate():\n'
            '    with pytest.raises(ValueError):\n'
            '        convert_currency(100.0, 0.0)\n',
            encoding="utf-8"
        )

        task_id = "task-p3-e2e-mission"
        repo_id = "unfamiliar-currency-repo"

        # --- A. INITIAL PLANNING & IMPACT ANALYSIS ---
        state = {
            "task_id": task_id,
            "repository_id": repo_id,
            "user_goal": "Fix zero division bug in convert_currency and raise ValueError",
            "workspace_path": str(ws_path),
            "repository_context": {
                "summary": {"backend": "Python Library", "test_command": "pytest"},
                "files": ["converter/calculator.py", "test_converter.py"],
            },
            "observations": [],
            "failure_history": [],
            "iteration_count": 1,
            "retry_count": 0,
        }

        impact_res = impact_analysis_node(state)
        state.update(impact_res)
        plan_res = plan_task(state)
        state.update(plan_res)
        assert len(state["plan"]) >= 4

        # --- B. FIRST VERIFICATION ATTEMPT (Fails due to initial defect) ---
        state["files_changed"] = ["converter/calculator.py"]
        ver_res_1 = verify_solution(state)
        state.update(ver_res_1)
        assert state["verification_status"] == "failed"
        assert state["test_results"]["failed"] >= 1

        # --- C. AUTONOMOUS DEBUGGING & ROOT CAUSE ANALYSIS ---
        debug_res = debug_failure(state)
        state.update(debug_res)
        assert len(state["failure_history"]) == 1
        fail_rec = state["failure_history"][0]
        assert fail_rec["category"] in ["runtime", "test_assertion"]
        assert "calculator.py" in str(fail_rec["suspect_file"]) or "test_converter.py" in str(fail_rec["suspect_file"])
        assert len(fail_rec["hypothesis"]) > 0

        # --- D. DYNAMIC REPLANNING ---
        replan_res = replan_step(state)
        state.update(replan_res)
        assert state["retry_count"] == 1
        assert len(state["plan"]) >= 3

        # --- E. EXECUTE TARGETED REPAIR ---
        # Apply the fix to calculator.py
        calc_file.write_text(
            'def convert_currency(amount: float, rate: float) -> float:\n'
            '    if rate <= 0.0:\n'
            '        raise ValueError("Conversion rate must be positive.")\n'
            '    return amount / rate\n',
            encoding="utf-8"
        )

        # --- F. SECOND VERIFICATION ATTEMPT (Passes!) ---
        ver_res_2 = verify_solution(state)
        state.update(ver_res_2)
        assert state["verification_status"] == "verified"
        assert state["test_results"]["passed"] == 2
        assert state["test_results"]["failed"] == 0

        # --- G. ROUTING & FINALIZATION ---
        next_route = should_continue_or_finalize(state)
        assert next_route == "finalize"

        final_res = finalize_task(state)
        report = final_res["final_result"]

        assert report["status"] == "verified"
        assert report["evidence"]["tests"]["passed"] == 2
        assert report["failures_diagnosed"] == 1

        # --- H. VERIFY PERMANENT KNOWLEDGE ACQUISITION ---
        # Verify episodic memory was recorded
        recalled_task = mem_store.get_task_memory(task_id)
        assert recalled_task is not None
        assert recalled_task.test_status == "verified"
        assert "converter/calculator.py" in recalled_task.files_modified

        # Verify proven fix pattern was learned into long-term engineering memory!
        decisions = eng_store.get_decisions(repo_id, category="proven_fix")
        assert len(decisions) >= 1
        assert "calculator.py" in decisions[0].subject or "calculator.py" in decisions[0].decision
