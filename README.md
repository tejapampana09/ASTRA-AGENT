# ASTRA 2.0 — Autonomous Software Engineering Agent

ASTRA 2.0 is a production-grade autonomous software engineering agent system. It autonomously inspects repositories, plans complex modifications, edits code, executes tests in isolated environments, analyzes errors, replans, verifies results with real evidence, and prepares pull requests.

## Architecture

- **Terminal CLI**: Rich interactive console REPL and direct single-shot autonomous execution (like Gemini CLI / Claude Code).
- **Orchestration**: LangGraph StateGraph workflow with explicit cycle limits, risk assessment, automated debugging, and replanning loops.
- **Agent Runtime**: OpenHands Software Agent SDK integration adapter providing isolated workspace execution, file editing, and terminal sandboxing.
- **Models**: Supports local Ollama (`qwen2.5-coder`) and Cloud Gemini (`gemini-2.5-flash` / `gemini-1.5-pro`).
- **Database & Persistence**: Instant local SQLite fallback or PostgreSQL for full persistence and audit history.

## Quickstart (Terminal CLI)

### 1. Interactive Mode (REPL)
Launch ASTRA interactively:
```bash
python astra.py
# or on Windows:
.\astra.bat
```

Inside the REPL, type your natural language goal or use slash commands:
- `/help` - Show available commands
- `/model [ollama|gemini]` - Switch active LLM
- `/mode [auto|guided]` - Switch between fully autonomous and human-in-the-loop modes
- `/diff` - Inspect modified files and git diffs
- `/history` - View recent events and reasoning steps
- `/repo <path>` - Set target repository workspace
- `/new` - Start a fresh session
- `/exit` - Exit ASTRA

### 2. Single-shot Autonomous Execution
Pass your goal directly from the command line:
```bash
python astra.py "Fix authentication error in auth.py and run pytest" --model ollama
# or using Gemini:
python astra.py "Implement user profile API endpoint with unit tests" --model gemini
```
