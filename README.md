# ASTRA V5 — Hardened Autonomous Software Engineering Agent

ASTRA is a local-first, hardened, autonomous software engineering runtime and desktop environment. It inspects local projects, plans surgical modifications, executes shell commands and file tools within a defense-in-depth security perimeter, autonomously verifies code changes with independent multi-language verifiers, and handles LLM provider quota exhaustion with adaptive failover.

---

## 🏗️ Architecture

```
                    ASTRA DESKTOP (Electron + React)
                                │
               IPC (Validated) / Local REST + WebSocket
                                │
                                ▼
                    ASTRA RUNTIME (FastAPI)
         (127.0.0.1 Binding | Strict CORS | Token Auth | Session WS)
                                │
               ┌────────────────┼────────────────┐
               ▼                ▼                ▼
         CONTROLLER (v5)     COGNITIVE STATE   SESSION & DB (SQLite)
               │                │                │
               ▼                ▼                ▼
           PLANNER         PROGRESS TRACKER   CHECKPOINTS (Containment)
               │
               ▼
           LLM ROUTER & QUOTA CIRCUIT BREAKER
     (Adaptive Fallback: Gemini ⮂ Groq ⮂ Ollama | No Circular Loops)
               │
               ▼
           TOOL REGISTRY & DEFENSE-IN-DEPTH SECURITY
     (Command Chaining Checks | Secret Redaction | Output Bounding)
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
        INDEPENDENT MULTI-LANGUAGE VERIFIER
               │
         ┌─────┴─────┐
         ▼           ▼
       PASS         FAIL / UNAVAILABLE
         │           │
       DONE       FIX LOOP (Max Attempts / Stagnation Detection)
```

---

## 🚀 Quickstart

### 1. Prerequisites
- **Python**: 3.10, 3.11, 3.12, or 3.13
- **Node.js**: 18.x or later (tested on Node v20/v24)
- **Local Ollama** (Optional for local-first offline execution):
  - Download from [ollama.com](https://ollama.com)
  - Pull a coding model:
    ```bash
    ollama pull qwen2.5-coder:7b
    ```

### 2. Python Environment Setup
```bash
# Install Python dependencies
pip install -r requirements.txt
```

### 3. Desktop Application Setup & Build
```bash
cd desktop
npm install
npm run build
npm run build:electron
npm start
```
Double-clicking `astra_desktop.bat` also automatically launches the runtime and desktop application.

### 4. CLI Mode
Interactive Terminal REPL:
```bash
python astra.py
```

Headless API Server:
```bash
python astra.py --serve --port 8765
```

---

## 🛡️ Security Hardening & Safeguards

### Electron Security
- `webSecurity: true` and `allowRunningInsecureContent: false` strictly enforced.
- `nodeIntegration: false` and `contextIsolation: true` preserve process boundaries.
- Navigation restricted via `will-navigate` to trusted application destinations only.
- Window opening restricted with `setWindowOpenHandler` denying arbitrary popups and routing trusted links to default browser via `shell.openExternal`.
- IPC calls validated (e.g. `shell:openPath` rejects non-strings and non-existent targets).
- Strict Content Security Policy (CSP) headers applied in `index.html`.

### Terminal & Shell Execution Security
- **Command Operator Parsing**: Chained shell commands (`&&`, `;`, `|`, `||`, `&`) are tokenized and every individual sub-command is verified against dangerous patterns.
- **Fail-Closed Permission Model**: High-risk operations (disk wiping, system manipulation, fork bombs, forced git pushes) are classified as `DANGEROUS` and blocked unless explicit interactive approval is granted.
- **Sensitive Token Redaction**: Output from commands, tools, and error messages is filtered through automated redaction expressions, preventing API keys (`gsk_*`, `AIzaSy*`, `sk-*`, `Bearer *`, etc.) from leaking into logs or LLM context.
- **Pipe Buffer Deadlock Prevention**: Subprocess execution uses `communicate()` with non-blocking threads to continually drain pipes, preventing OS pipe buffer deadlocks.
- **Bounded Buffer Protection**: Output is bounded (default 65,536 chars) to prevent runaway processes from causing memory exhaustion.

### Backend API Security
- Bound to loopback interface `127.0.0.1` by default.
- Strict CORS configuration using explicit allowed origins (defaulting to local dev/desktop hosts; no wildcard `*`).
- Optional token authentication (`ASTRA_API_TOKEN` / header `X-Astra-Token`) on mutating endpoints.
- Path traversal validation on `/api/workspace/file` with explicit HTTP 403 Forbidden responses.
- WebSocket session isolation: session events route strictly to session subscribers.

### Quota-Aware LLM Routing & Circuit Breaker
- Centralized `QuotaCircuitBreaker` tracking error categories (`RATE_LIMITED`, `QUOTA_EXHAUSTED`, `AUTH_ERROR`).
- Circular fallback prevention: providers attempted in a request chain are never re-entered.
- Healthy local Ollama fallback when cloud provider quotas are exhausted.
- Exponential backoff with jitter on transient network/5xx errors.

### Checkpoints and Rollback Safety
- Strict path containment checks on snapshot and rollback operations (`relative_to` validation).
- Absolute or traversal paths outside workspace are blocked from creation or deletion.
- Pre-existing workspace files created prior to the session are safeguarded from deletion.

---

## ⚙️ Configuration Reference (`.env`)

```ini
# LLM Provider Keys
GROQ_API_KEY=your_groq_key
GEMINI_API_KEY=your_gemini_key

# Default Model Selection
ASTRA_MODEL=gemini-3.5-flash-lite

# Local Ollama URL
OLLAMA_BASE_URL=http://localhost:11434

# Server & Security Controls
ASTRA_HOST=127.0.0.1
ASTRA_PORT=8765
ASTRA_API_TOKEN=

# Allowed CORS Origins
ASTRA_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:8765,http://127.0.0.1:8765,app://-

# Execution Limits
ASTRA_MAX_ITERATIONS=30
ASTRA_COMMAND_TIMEOUT=120
ASTRA_MAX_OUTPUT_CHARS=65536
ASTRA_CIRCUIT_BREAKER=true
```

---

## 🧪 Verification & Test Suite

Run the full automated test suite:
```bash
python -m pytest -v
```

Run byte-compilation check:
```bash
python -m compileall -q astra tests
```

Build desktop frontend & Electron scripts:
```bash
cd desktop
npm run build
npm run build:electron
```


## Audit fixes and runtime limits

See [AUDIT.md](AUDIT.md) for the October 25, 2026 audit, validated fixes, Gemini
request-budget configuration, fixed workspace trust roots, desktop authentication,
and testing limitations. The usage dashboard shows recorded usage; runtime settings
now update the backend. New sessions have a cumulative request budget by default.
