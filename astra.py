#!/usr/bin/env python
"""
ASTRA 2.0 CLI Launcher.
Interactive Autonomous Software Engineer in your terminal.
Usage:
    python astra.py
    python astra.py "Fix authentication bug and push it"
    python astra.py --model gemini
"""
import os
import sys
from pathlib import Path

# Configure UTF-8 encoding for Windows terminals
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Silence raw server logs in CLI mode
os.environ["ASTRA_CLI_MODE"] = "1"
os.environ["LITELLM_LOG"] = "ERROR"

# Add backend to sys.path
backend_dir = Path(__file__).resolve().parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.cli import main

if __name__ == "__main__":
    main()
