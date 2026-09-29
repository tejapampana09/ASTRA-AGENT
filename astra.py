#!/usr/bin/env python
"""
ASTRA 3.0 Launcher.
Next-generation Autonomous Software Engineering Agent.
"""
import os
import sys

# Configure UTF-8 encoding on Windows
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from astra.cli import main

if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
