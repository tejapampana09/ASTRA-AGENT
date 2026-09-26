#!/usr/bin/env python
"""
ASTRA 2.0 CLI Launcher.
Interactive Autonomous Software Engineer in your terminal.
Usage:
    python astra.py
    python astra.py "Fix authentication bug and push it"
    python astra.py --model gemini
"""
import sys
from pathlib import Path

# Add backend to sys.path
backend_dir = Path(__file__).resolve().parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.cli import main

if __name__ == "__main__":
    main()
