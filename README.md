# ASTRA 3.0 — Autonomous Software Engineering Agent

A clean, modern, lightweight autonomous coding agent built from scratch. Inspects codebases, plans multi-step modifications, edits code surgically, runs test suites, debugs errors, and verifies results.

## Key Features

- **⚡ Sub-Second Launch**: Instant startup (< 0.2s) without heavy database or indexing bloat.
- **🛡️ Fail-Fast & Never Hangs**: Real-time health-checks prevent infinite retry loops on dead or offline model endpoints.
- **🔌 Multi-Provider LLM Engine**:
  - **Google Gemini** (Gemini 2.5 Flash / Pro via modern `google-genai` SDK)
  - **Local Ollama** (e.g., `qwen2.5-coder:3b`, `deepseek-coder`)
  - **TejaAI Fine-Tuned Server** (Colab GPU with Cloudflare tunnel)
  - **OpenAI / Claude / OpenRouter** (via LiteLLM)
- **🛠️ Built-in Software Engineering Tools**:
  - `read_file`, `write_file`, `edit_file`
  - `list_dir`, `search_code`
  - `run_command` (runs test suites, linters, git, npm, etc.)
  - `git_status`, `git_diff`
- **🖥️ Rich Terminal Experience**:
  - Interactive REPL with slash commands
  - Direct goal CLI execution (`python astra.py "<goal>"`)
  - Colorized diffs and live reasoning steps

---

## Quickstart

### 1. Configuration
Open `.env` and set your API key or model:
```bash
# Using Google Gemini (Recommended)
GEMINI_API_KEY=your_key_here

# Or Local Ollama
ASTRA_MODEL=ollama/qwen2.5-coder:3b

# Or Fine-Tuned Colab Server
TEJA_MODEL_URL=https://your-tunnel.trycloudflare.com/v1
ASTRA_MODEL=teja-gemma
```

### 2. Interactive Mode (REPL)
```bash
python astra.py
# or on Windows:
.\astra.bat
```

Inside the REPL:
- Type any natural language goal: `Fix failing test in test_auth.py and run pytest`
- `/help` - Show available commands
- `/model [gemini|ollama|teja-gemma]` - Switch active model
- `/status` - Check git status and modified files
- `/diff` - View colorized git diff of your changes
- `/files` - Browse repository structure
- `/run <cmd>` or `!<cmd>` - Run shell commands directly in workspace
- `/clear` - Clear screen
- `/exit` - Exit ASTRA

### 3. Direct Goal Execution
```bash
python astra.py "Implement password validation in auth.py and verify with pytest"
```

---

## Running Tests
To verify ASTRA's tool execution engine:
```bash
python -m pytest tests/test_agent.py -v
```
