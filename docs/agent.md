# ASTRA 2.0 — Agent State & LangGraph Workflow

## Strongly Typed Agent State

`AstraAgentState` contains:
- `task_id`: Unique identifier for the engineering task.
- `repository_id`: Associated repository metadata.
- `user_goal`: High-level prompt provided by the engineer.
- `repository_context`: Detected languages, frameworks, package managers, and file hierarchy.
- `plan`: Structured multi-step execution plan.
- `current_step`: Active step index.
- `observations`: Chronological execution timeline and agent thoughts.
- `tool_calls`: Log of all invoked tools with arguments and results.
- `files_changed`: List of modified files.
- `test_results`: Empirical test counts (passed, failed, errors, tracebacks).
- `build_results`: Build verification status.
- `verification_status`: `verified`, `failed`, or `uncertain`.
- `failure_history`: Historical log of failing attempts to prevent repetitive cycles.
- `approval_required` / `approval_status`: Human-in-the-loop approval tracking.
- `final_result`: Verifiable execution evidence.

## Safety & Iteration Limits

Infinite loops are strictly prevented via:
- `MAX_ITERATIONS` (default: 15)
- `MAX_TOOL_CALLS` (default: 50)
- `MAX_RETRIES` (default: 3)
- `COMMAND_TIMEOUT_SECONDS` (default: 180s)
