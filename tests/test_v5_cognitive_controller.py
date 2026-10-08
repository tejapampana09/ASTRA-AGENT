"""ASTRA V5 Cognitive Agent Controller & Execution Architecture Test Suite.

Validates:
1. Natural language task classification across realistic developer requests
2. Investigation-first debugging enforcement (no premature code mutation)
3. Evidence-driven reasoning and hypothesis tracking
4. Controller tool action gating and duplicate loop prevention
5. Stagnation detection and dynamic replanning
6. Independent verification & failure recovery
7. Cognitive state persistence and resume continuity
8. Conversation continuity across follow-up queries
9. Rejection of premature completion (controller owns completion)
10. Full cognitive loop end-to-end execution
"""
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List
import pytest

from astra.agent import AstraAgent
from astra.controller import DeterministicAgentController, TaskModel, classify_task_intent
from astra.events import AgentState, ControllerPhase, EventType, event_bus
from astra.llm import LLMResponse
from astra.progress import ProgressAction
from astra.session import SessionManager
from astra.state import CognitiveState, TaskState, TaskType
from astra.tools import ToolRegistry, ToolResult
from astra.verifier import IndependentVerifier, VerificationResult


@pytest.fixture
def temp_workspace():
    td = tempfile.mkdtemp()
    ws = Path(td).resolve()
    db_file = ws / "test_session.db"
    sess_mgr = SessionManager(db_path=db_file)
    yield ws, sess_mgr
    shutil.rmtree(td, ignore_errors=True)


# =====================================================================
# 1. NATURAL LANGUAGE TASK CLASSIFICATION TESTS
# =====================================================================

def test_task_classification_debug_queries():
    """Verify bug, broken, crash, and failing requests classify as DEBUG."""
    debug_queries = [
        "bro login page is broken",
        "why is the websocket disconnecting?",
        "fix the login bug",
        "find why tests are failing and fix them",
        "the WhatsApp reply isn't sending",
        "debug the 500 error in auth router",
        "fix traceback in calculate_tax",
    ]
    for q in debug_queries:
        model = classify_task_intent(q)
        assert model.task_type == TaskType.DEBUG, f"Query '{q}' was classified as {model.task_type.value}, expected DEBUG"


def test_task_classification_implementation_queries():
    """Verify feature addition queries classify as IMPLEMENTATION."""
    impl_queries = [
        "add Google login",
        "add dark mode",
        "create a health check endpoint",
        "implement password reset with jwt",
        "integrate Stripe payment webhook",
        "build a rate limiting middleware",
    ]
    for q in impl_queries:
        model = classify_task_intent(q)
        assert model.task_type == TaskType.IMPLEMENTATION, f"Query '{q}' was classified as {model.task_type.value}, expected IMPLEMENTATION"


def test_task_classification_documentation_queries():
    """Verify architecture and explanation queries classify as DOCUMENTATION."""
    doc_queries = [
        "explain the architecture",
        "explain this project's architecture",
        "how does the authentication pipeline work?",
        "document the database schema",
        "what is the directory structure and main entry point?",
        "overview of the payment integration",
    ]
    for q in doc_queries:
        model = classify_task_intent(q)
        assert model.task_type == TaskType.DOCUMENTATION, f"Query '{q}' was classified as {model.task_type.value}, expected DOCUMENTATION"


def test_task_classification_refactor_queries():
    """Verify cleanup and reorganization queries classify as REFACTOR."""
    refactor_queries = [
        "clean up this authentication module",
        "clean up this module",
        "refactor user service to use async await",
        "restructure database models into separate files",
        "simplify calculate_totals logic",
    ]
    for q in refactor_queries:
        model = classify_task_intent(q)
        assert model.task_type == TaskType.REFACTOR, f"Query '{q}' was classified as {model.task_type.value}, expected REFACTOR"


def test_task_classification_investigation_queries():
    """Verify audit and verification queries classify as INVESTIGATION."""
    investigation_queries = [
        "check whether the API flow is correct",
        "investigate memory consumption in worker pool",
        "audit permissions in user controller",
        "trace the websocket connection handshake",
    ]
    for q in investigation_queries:
        model = classify_task_intent(q)
        assert model.task_type == TaskType.INVESTIGATION, f"Query '{q}' was classified as {model.task_type.value}, expected INVESTIGATION"


def test_task_classification_conversational():
    """Verify conversational greetings classify as CONVERSATION."""
    greetings = ["hi", "hello", "hey", "who are you", "what can you do"]
    for g in greetings:
        model = classify_task_intent(g)
        assert model.task_type == TaskType.CONVERSATION, f"Greeting '{g}' expected CONVERSATION"


# =====================================================================
# 2. INVESTIGATION-FIRST DEBUGGING ENFORCEMENT
# =====================================================================

def test_investigation_before_mutation_enforced(temp_workspace):
    """In a DEBUG task, mutating files before any investigation must be blocked."""
    workspace, sess_mgr = temp_workspace
    sess_id = sess_mgr.create_session(str(workspace), title="Investigate First Test")

    controller = DeterministicAgentController(
        workspace_path=workspace,
        session_id=sess_id,
        goal="The WhatsApp reply isn't sending",
        session_manager=sess_mgr,
    )
    controller.start_task("The WhatsApp reply isn't sending")
    assert controller.task_type == TaskType.DEBUG
    assert controller.phase == ControllerPhase.INVESTIGATE

    # Target code file exists
    src_file = workspace / "whatsapp.py"
    src_file.write_text("def send_reply(msg):\n    pass\n")

    # Attempt premature mutation before reading or searching code
    allowed, reason = controller.action_allowed("edit_file", {
        "file_path": "whatsapp.py",
        "target_snippet": "pass",
        "replacement_snippet": "return True",
    })
    assert allowed is False
    assert "investigation-first rule" in reason.lower()

    # Step 1: Perform investigation (read_file)
    read_res = controller.execute_action("read_file", {"file_path": "whatsapp.py"})
    assert read_res.success is True
    controller.record_and_evaluate_action("read_file", {"file_path": "whatsapp.py"}, read_res)

    # Step 2: Now that investigation has occurred, mutation is allowed
    allowed_after, reason_after = controller.action_allowed("edit_file", {
        "file_path": "whatsapp.py",
        "target_snippet": "pass",
        "replacement_snippet": "return True",
    })
    assert allowed_after is True
    assert reason_after == ""


# =====================================================================
# 3. EVIDENCE & HYPOTHESIS TRACKING
# =====================================================================

def test_evidence_and_hypothesis_lifecycle(temp_workspace):
    """Track evidence accumulation and hypothesis status transitions."""
    workspace, sess_mgr = temp_workspace
    sess_id = sess_mgr.create_session(str(workspace), title="Evidence Test")

    controller = DeterministicAgentController(
        workspace_path=workspace,
        session_id=sess_id,
        goal="why is the websocket disconnecting?",
        session_manager=sess_mgr,
    )
    controller.start_task("why is the websocket disconnecting?")

    # Add evidence
    e1 = controller.add_evidence("WebSocket handshake completes with code 101", source="server.py")
    e2 = controller.add_evidence("Heartbeat timeout triggers after 30 seconds of inactivity", source="client.ts")
    assert e1 == "E1"
    assert e2 == "E2"
    assert len(controller.cognitive_state.evidence) == 2
    assert "WebSocket handshake completes with code 101" in controller.cognitive_state.known_facts

    # Form hypotheses
    h1 = controller.add_hypothesis("Client heartbeat ping is not sent periodically")
    h2 = controller.add_hypothesis("Server rejects ping frame due to payload mismatch")
    assert h1 == "H1"
    assert h2 == "H2"
    assert controller.cognitive_state.hypotheses[0]["status"] == "UNTESTED"

    # Test and update hypothesis
    controller.update_hypothesis(h1, status="CONFIRMED", evidence_id=e2)
    controller.update_hypothesis(h2, status="REJECTED")

    assert controller.cognitive_state.hypotheses[0]["status"] == "CONFIRMED"
    assert e2 in controller.cognitive_state.hypotheses[0]["evidence_ids"]
    assert controller.cognitive_state.hypotheses[1]["status"] == "REJECTED"


# =====================================================================
# 4. ACTION GATING & DUPLICATE PREVENTION
# =====================================================================

def test_tool_action_gating_loop_detection(temp_workspace):
    """Ensure identical repeated tool calls are gated and rejected."""
    workspace, sess_mgr = temp_workspace
    sess_id = sess_mgr.create_session(str(workspace), title="Gating Test")

    controller = DeterministicAgentController(
        workspace_path=workspace,
        session_id=sess_id,
        goal="add health check endpoint",
        session_manager=sess_mgr,
    )

    args = {"file_path": "health.py", "content": "def health(): return {'status': 'ok'}"}
    res = controller.execute_action("create_file", args)
    controller.record_and_evaluate_action("create_file", args, res)

    # Calling exact same action immediately again must be blocked by controller
    controller.record_and_evaluate_action("create_file", args, res)
    allowed, reason, guidance = controller.validate_and_prepare_action("create_file", args)
    assert allowed is False
    assert "duplicate" in reason.lower()
    assert guidance is not None


# =====================================================================
# 5. STAGNATION DETECTION & REPLANNING
# =====================================================================

def test_stagnation_triggers_replanning(temp_workspace):
    """4 consecutive read actions without code modification must trigger REPLAN."""
    workspace, sess_mgr = temp_workspace
    sess_id = sess_mgr.create_session(str(workspace), title="Stagnation Test")

    controller = DeterministicAgentController(
        workspace_path=workspace,
        session_id=sess_id,
        goal="Fix broken router",
        session_manager=sess_mgr,
    )
    controller.start_task("Fix broken router")

    (workspace / "a.py").write_text("a = 1")
    (workspace / "b.py").write_text("b = 2")
    (workspace / "c.py").write_text("c = 3")
    (workspace / "d.py").write_text("d = 4")

    # Record 4 read steps
    for f in ["a.py", "b.py", "c.py", "d.py"]:
        res = controller.execute_action("read_file", {"file_path": f})
        report = controller.record_and_evaluate_action("read_file", {"file_path": f}, res)

    # Controller should have diagnosed stagnation and triggered replan
    assert controller.phase in (ControllerPhase.DIAGNOSE, ControllerPhase.REPLAN)
    assert any("Resolve Blocker" in s.title for s in controller.task_state.plan.steps)


# =====================================================================
# 6. INDEPENDENT VERIFICATION OUTSIDE LLM REASONING
# =====================================================================

def test_independent_verification_pass_and_fail(temp_workspace):
    """Controller verification must deterministically set DONE on pass and DIAGNOSE on fail."""
    workspace, sess_mgr = temp_workspace
    sess_id = sess_mgr.create_session(str(workspace), title="Verification Test")

    controller = DeterministicAgentController(
        workspace_path=workspace,
        session_id=sess_id,
        goal="Fix syntax error",
        session_manager=sess_mgr,
    )

    # 1. Broken syntax file
    broken = workspace / "logic.py"
    broken.write_text("def broken(:\n    return 42\n")
    controller.task_state.files_modified.add("logic.py")

    vres, prep = controller.verify()
    assert vres.passed is False
    assert controller.phase == ControllerPhase.REPLAN
    assert vres.phase == "syntax_check"

    # 2. Fix the syntax
    broken.write_text("def broken():\n    return 42\n")
    vres2, prep2 = controller.verify()
    assert vres2.passed is True
    assert controller.phase == ControllerPhase.DONE
    assert "passed" in vres2.summary.lower()


# =====================================================================
# 7. SESSION PERSISTENCE & RESUME
# =====================================================================

def test_cognitive_state_persistence_and_resume(temp_workspace):
    """Verify CognitiveState survives restarts and resumes from current objective."""
    workspace, sess_mgr = temp_workspace
    sess_id = sess_mgr.create_session(str(workspace), title="Resume Cognitive Test")

    c1 = DeterministicAgentController(
        workspace_path=workspace,
        session_id=sess_id,
        goal="The WhatsApp reply isn't sending",
        session_manager=sess_mgr,
    )
    c1.start_task("The WhatsApp reply isn't sending")
    c1.add_evidence("send_reply is invoked but webhook returns 401", source="webhook.log")
    c1.add_hypothesis("Bearer token in header is expired")
    c1.set_objective("Inspect token refresh handler in auth.py")

    # Simulate restart: create c2 from same session_id
    c2 = DeterministicAgentController(
        workspace_path=workspace,
        session_id=sess_id,
        session_manager=sess_mgr,
    )
    assert c2.cognitive_state.goal == "The WhatsApp reply isn't sending"
    assert c2.task_type == TaskType.DEBUG
    assert len(c2.cognitive_state.evidence) == 1
    assert "send_reply is invoked" in c2.cognitive_state.evidence[0]["fact"]
    assert len(c2.cognitive_state.hypotheses) == 1
    assert c2.cognitive_state.current_objective == "Inspect token refresh handler in auth.py"


# =====================================================================
# 8. CONVERSATION CONTINUITY FOR FOLLOW-UP QUESTIONS
# =====================================================================

def test_conversation_continuity_follow_up(temp_workspace):
    """Follow-up questions maintain task context without resetting cognitive state."""
    workspace, sess_mgr = temp_workspace
    sess_id = sess_mgr.create_session(str(workspace), title="Follow-up Test")

    controller = DeterministicAgentController(
        workspace_path=workspace,
        session_id=sess_id,
        goal="fix login",
        session_manager=sess_mgr,
    )
    controller.start_task("fix login")
    assert controller.task_type == TaskType.DEBUG

    # User follow-up query
    follow_up_model = controller.start_task("what about the refresh token?", is_follow_up=True)
    assert follow_up_model.task_type == TaskType.DEBUG
    assert "refresh token" in controller.cognitive_state.current_objective.lower()
    assert any("refresh token" in f.lower() for f in controller.cognitive_state.known_facts)


# =====================================================================
# 9. REJECTION OF PREMATURE COMPLETION
# =====================================================================

def test_no_premature_completion(temp_workspace):
    """Controller must reject completion when an actionable task has unverified edits or no action taken."""
    workspace, sess_mgr = temp_workspace
    sess_id = sess_mgr.create_session(str(workspace), title="Premature Completion Test")

    controller = DeterministicAgentController(
        workspace_path=workspace,
        session_id=sess_id,
        goal="Fix the login bug",
        session_manager=sess_mgr,
    )
    controller.start_task("Fix the login bug")

    # 1. Model says it's done without having done any investigation or edits
    is_done, reason = controller.check_completion("I have fixed the issue. You should run pytest.", files_changed=[])
    assert is_done is False
    assert "requires taking action" in reason.lower()

    # 2. Model edited file but verification hasn't passed
    is_done2, reason2 = controller.check_completion("I edited the file.", files_changed=["auth.py"])
    assert is_done2 is False
    assert "verification" in reason2.lower()


# =====================================================================
# 10. FULL AUTONOMOUS COGNITIVE LOOP END-TO-END
# =====================================================================

class MockCognitiveLLM:
    """Simulates an autonomous LLM operating under controller guidance."""

    def __init__(self):
        self.turns = 0

    def complete(self, messages: List[Dict[str, Any]], tools=None, temperature=0.1, model=None) -> LLMResponse:
        self.turns += 1

        # Turn 1: Investigate file
        if self.turns == 1:
            return LLMResponse(
                content="I need to investigate the calculation function first to understand the bug.",
                tool_calls=[{
                    "id": "tc_1",
                    "type": "function",
                    "function": {
                        "name": "read_file",
                        "arguments": {"file_path": "discount.py"},
                    },
                }],
            )

        # Turn 2: Apply surgical fix
        if self.turns == 2:
            return LLMResponse(
                content="The discount applies 50% instead of 20%. I will fix it now.",
                tool_calls=[{
                    "id": "tc_2",
                    "type": "function",
                    "function": {
                        "name": "edit_file",
                        "arguments": {
                            "file_path": "discount.py",
                            "target_snippet": "return price * 0.5",
                            "replacement_snippet": "return price * 0.2",
                        },
                    },
                }],
            )

        # Turn 3: Complete work
        return LLMResponse(
            content="I have updated discount.py with the correct 20% calculation.",
            tool_calls=[],
        )


def test_full_autonomous_cognitive_loop_e2e(temp_workspace, monkeypatch):
    """Test full loop: USER -> UNDERSTAND -> INVESTIGATE -> EXECUTE -> VERIFY -> DONE."""
    workspace, sess_mgr = temp_workspace
    (workspace / "discount.py").write_text("def apply_discount(price):\n    return price * 0.5\n")
    
    tests_dir = workspace / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_discount.py").write_text(
        "from discount import apply_discount\n\ndef test_discount():\n    assert apply_discount(100) == 20\n"
    )

    agent = AstraAgent(workspace_path=workspace, session_manager=sess_mgr, max_iterations=6)
    mock_llm = MockCognitiveLLM()
    monkeypatch.setattr(agent.llm, "complete", mock_llm.complete)

    result = agent.run("Find why tests are failing and fix them")

    assert result["status"] == "completed"
    assert "discount.py" in result["files_modified"]
    assert result["verification"] == "passed"
    assert "return price * 0.2" in (workspace / "discount.py").read_text()


def test_realistic_natural_language_queries():
    """Verify Section 24 realistic user prompts classify into appropriate task types naturally."""
    expected = {
        "fix the login bug": TaskType.DEBUG,
        "why is the websocket disconnecting?": TaskType.DEBUG,
        "add dark mode": TaskType.IMPLEMENTATION,
        "explain this project's architecture": TaskType.DOCUMENTATION,
        "find why tests are failing and fix them": TaskType.DEBUG,
        "the WhatsApp reply isn't sending": TaskType.DEBUG,
        "clean up this module": TaskType.REFACTOR,
        "check whether the API flow is correct": TaskType.INVESTIGATION,
    }
    for query, expected_type in expected.items():
        model = classify_task_intent(query)
        assert model.task_type == expected_type, f"Query '{query}' classified as {model.task_type}, expected {expected_type}"
        if expected_type == TaskType.DEBUG:
            assert DeterministicAgentController.requires_investigation_first(model.task_type) is True


def test_code_summary_requires_file_inspection_not_just_listing(temp_workspace):
    """Verify that asking to summarize folder codes requires reading files, rejecting mere file listings."""
    workspace, sess_mgr = temp_workspace
    (workspace / "main.py").write_text("def run():\n    print('core app running')\n")
    session_id = sess_mgr.create_session(str(workspace), "test-model")

    goal = "hey bro can you summarize my folder codes"
    controller = DeterministicAgentController(
        workspace_path=workspace,
        session_id=session_id,
        goal=goal,
        session_manager=sess_mgr,
    )
    controller.start_task(goal)

    # 1. Simulate LLM merely listing directory
    list_res = controller.execute_action("list_dir", {"path": "."})
    controller.record_and_evaluate_action("list_dir", {"path": "."}, list_res)

    # Merely returning the file listing must be REJECTED by the controller
    mere_listing = "# Folder Contents Summary\nThe current directory contains the following files:\n- .env\n- main.py\n- README.md"
    completed, reason = controller.check_completion(mere_listing, [])
    assert completed is False
    assert "not inspected any actual code files" in reason or "listing" in reason

    # 2. Simulate reading the actual code file
    read_res = controller.execute_action("read_file", {"file_path": "main.py"})
    controller.record_and_evaluate_action("read_file", {"file_path": "main.py"}, read_res)

    # Now provide a meaningful explanation of code functionality
    rich_summary = (
        "### Module Architecture\n"
        "The `main.py` entry point implements the core execution pipeline with the `run()` function.\n"
        "It initializes the service runtime and handles application bootstrap."
    )
    completed, reason = controller.check_completion(rich_summary, [])
    assert completed is True
