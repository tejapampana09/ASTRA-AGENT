@echo off
title ASTRA V4 Standalone Desktop
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

cd /d "%~dp0desktop"

echo [ASTRA V4] Launching ASTRA V4 Desktop Window...
npx electron dist-electron/main.js
