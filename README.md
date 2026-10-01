# ASTRA V4 — Standalone Autonomous Software Engineering Agent

ASTRA V4 is a local-first, production-oriented autonomous software engineering agent built from scratch. It inspects local projects, plans surgical modifications, edits source code, runs terminal builds/linters/tests, autonomously fixes failures, and verifies completion with independent verifiers before declaring success.

---

## 🏗️ Architecture

```
                    ASTRA DESKTOP
                         │
                  Electron + React (Echo AI Design)
                         │
              IPC / Localhost REST + WebSocket
                         │
                         ▼
                  ASTRA RUNTIME
                         │
              ┌──────────┼──────────┐
              ▼          ▼          ▼
          ORCHESTRATOR  CONTEXT   SESSION
              │          │          │
              ▼          ▼          ▼
           LLM ROUTER   SEARCH    STORAGE (SQLite)
              │
       ┌──────┼──────────────┐
       ▼      ▼              ▼
    Ollama  Gemini        TejaAI / Groq
              │
              ▼
          TOOL REGISTRY & SECURITY SANDBOX
              │
      ┌───────┼────────┬─────────┐
      ▼       ▼        ▼         ▼
    Files   Terminal   Git      Web
      │       │        │
      └───────┼────────┘
              ▼
          WORKSPACE
              │
              ▼
       INDEPENDENT VERIFICATION ENGINE
              │
        ┌─────┴─────┐
        ▼           ▼
      PASS         FAIL
        │           │
      DONE       FIX LOOP (Max 3 / Loop Detection)
```

---

## 🚀 Quickstart

### 1. Prerequisites
- **Python**: 3.10+ (tested on Python 3.12)
- **Node.js**: 18+ (tested on Node v24.19)
- **Local Ollama** (Recommended for local-first execution):
  - Download from [ollama.com](https://ollama.com)
  - Pull a coding model:
    ```bash
    ollama pull qwen2.5-coder:7b
    ```

### 2. Launch Standalone Desktop Application
Double-click `astra_desktop.bat` or run:
```bash
# Start desktop application
.\astra_desktop.bat

# Or manually:
cd desktop
npm start
```
The desktop app automatically detects and launches the local Python ASTRA runtime server on `http://127.0.0.1:8765`.

### 3. Launch CLI Mode (100% Backward Compatible)
Interactive Terminal REPL:
```bash
python astra.py
# or:
.\astra.bat
```

Direct Goal Execution:
```bash
python astra.py "Fix the failing test in calculator.py and verify with pytest"
```

Start ASTRA Runtime API Server independently:
```bash
python astra.py --serve
```

---

## 🦙 Ollama First-Class Integration

ASTRA V4 treats Ollama as a first-class local runtime:
- **Automatic Status Detection**: Real-time status indicator (`Ollama ● Connected` or `Ollama ● Disconnected`).
- **Dynamic Model Discovery**: Queries `http://localhost:11434/api/tags` to populate installed models in the dropdown.
- **Native Tool Calling**: Structured tool definitions sent directly to Ollama chat endpoint with automatic token/JSON fallback parsing.
- **Fail-Safe Offline Instructions**: Clear step-by-step guidance if the local daemon is not running.

---

## ⚙️ Configuration & Environment (`.env`)

```ini
# Primary Provider & Model
ASTRA_PROVIDER=ollama
ASTRA_MODEL=ollama/qwen2.5-coder:7b
OLLAMA_BASE_URL=http://localhost:11434

# Cloud LLM Backends (Optional)
GROQ_API_KEY=gsk_...
GEMINI_API_KEY=AQ...
TEJA_MODEL_URL=https://...trycloudflare.com/v1

# Security & Execution Limits
ASTRA_MAX_ITERATIONS=30
ASTRA_COMMAND_TIMEOUT=120
ASTRA_PERMISSION_MODE=balanced
```

### Permission Modes:
- **`balanced`** (default): Safe commands run automatically; dangerous commands (`rm -rf`, `format`, `git reset --hard`, `git push --force`) require interactive user approval.
- **`strict`**: Prompts the user before running any terminal command or deleting files.
- **`safe`**: Completely blocks destructive actions.

---

## 🛡️ Filesystem & Terminal Security
- **Path Traversal Protection**: Every file access is strictly validated against the active workspace root. Any attempt to escape via `../../` is blocked.
- **Secret Protection**: `.env`, private keys (`id_rsa`, `id_ed25519`, `*.key`), and sensitive credential files are shielded from unauthorized LLM reading.
- **Execution Limits**: Configurable timeouts on all commands, external tools, and LLM calls. Process kill and cancellation supported at any moment via the **STOP** button.

---

## 🧪 Comprehensive Testing Suite

ASTRA V4 includes unit, integration, and full end-to-end tests:
```bash
python -m pytest tests/ -v
```

### Verified Test Categories (35/35 passing):
- **Tool Registry & Security**: Path traversal escapes, sensitive file locks, destructive command classification.
- **Workspace Manager**: Project detection across Python, Node.js, React, TypeScript, Rust, Go.
- **Independent Verifier & Loop Detector**: AST checks, error categorization, 3-attempt loop detector.
- **Session Persistence**: SQLite session CRUD, messages, events, file modifications.
- **FastAPI Endpoints**: Health, models, workspace, sessions, tasks.
- **Section 41 E2E Test**: Intentionally broken project (`def add(a, b): return a - b`) autonomously diagnosed, surgically fixed (`return a + b`), and verified via pytest.

---

## 🖥️ UI Features & Echo Design Layout
- **Left Sidebar**:
  - `+ New Chat`, `Chat`, `Workspace`, `Models`, `Usage`
  - Session history grouped by `PINNED`, `TODAY`, `YESTERDAY`
  - Live Ollama connection card (`● Connected`)
  - Workspace switcher and user profile
- **Center Canvas**:
  - Glowing purple ambient top-right atmosphere
  - Central orbital logo & welcome banner
  - 3 Instant suggestion cards
  - Floating glowing input pill with model picker, workspace attachment, mic, and action button
- **Inspection Drawers**:
  - **Tool Calls & Sources**: Slide-over drawer with real-time tool trace
  - **Terminal**: Real-time process streaming
  - **Diff Viewer**: Line-by-line colored git diffs
  - **Model Catalog**: Multi-category model browser
  - **Usage Dashboard**: Visual token and request metrics
- **Approval Modal**: Interactive prompt for dangerous terminal operations.

---

## 🤝 Troubleshooting
- **Ollama Disconnected**: Run `ollama serve` in a terminal or launch the Ollama desktop application.
- **No Models Available**: Run `ollama pull qwen2.5-coder:7b`.
- **Port Conflict (8765)**: Set `ASTRA_PORT=8766` in `.env` or pass `--port 8766` to `python astra.py --serve`.
