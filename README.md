# ASTRA 2.0 — Autonomous Software Engineering Agent

ASTRA 2.0 is a production-grade autonomous software engineering agent system. It autonomously inspects repositories, plans complex modifications, edits code, executes tests in isolated environments, analyzes errors, replans, verifies results with real evidence, and prepares pull requests.

## Architecture

- **Orchestration**: LangGraph StateGraph workflow with explicit cycle limits, risk assessment, debugging, and human approval gates.
- **Agent Runtime**: OpenHands Software Agent SDK integration adapter providing isolated workspace execution, file editing, and terminal sandboxing.
- **Backend**: FastAPI with async background task management, Server-Sent Events (SSE) for live streaming, and REST APIs.
- **Database & Memory**: PostgreSQL with pgvector for project & semantic memory, Redis for task queueing & cache.
- **Frontend**: React + TypeScript engineering dashboard with real-time diff viewer, timeline, terminal streams, and approval modals.

## Quickstart

1. Copy `.env.example` to `.env` and configure your LLM API keys:
   ```bash
   cp .env.example .env
   ```
2. Start the services with Docker Compose:
   ```bash
   docker-compose up --build
   ```
3. Open the dashboard at `http://localhost:3000` or interact with the API at `http://localhost:8000/docs`.
