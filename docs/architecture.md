# ASTRA 2.0 — Architecture Specification

## Overview

ASTRA 2.0 is an autonomous software engineering agent built on top of the **OpenHands Software Agent SDK** and **LangGraph**, providing isolated repository intelligence, patch-based editing, terminal sandboxing, empirical verification, and human-in-the-loop approvals.

## System Diagram

```
User (Browser / CLI)
        ↓
    React Dashboard (TypeScript + Tailwind)
        ↓  (HTTP REST + SSE Events)
    FastAPI Gateway
        ↓
    Task Lifecycle Manager (Non-blocking async worker)
        ↓
    LangGraph Workflow Engine
        ├── UnderstandTask & LoadContext
        ├── Plan & RiskAssessment
        ├── Execute (OpenHands SDK Adapter)
        │       ├── FileEditorTool
        │       ├── TerminalTool
        │       └── GitTool
        ├── Observe & Change Tracking
        ├── Verifier (Pytest / Build / Lint / Git Diff)
        │       ├── PASS → Finalize Task
        │       └── FAIL → Autonomous Debugger
        └── Replan & Targeted Patch Loop
```

## Storage and Persistence

- **PostgreSQL + pgvector**: Durable metadata storage for tasks, steps, tool calls, file changes, verification runs, and semantic code embeddings.
- **Redis**: Background queue, task coordination, and distributed cache.
- **Isolated Workspaces**: Disk-isolated workspaces with Git support, path validation, and dirty worktree detection.
