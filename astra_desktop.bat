@echo off
title ASTRA V4 Standalone Desktop
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

cd /d "%~dp0desktop"

:: Terminate any orphaned process holding port 8765 from previous sessions
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8765 ^| findstr LISTENING 2^>nul') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo [ASTRA V4] Launching ASTRA V4 Desktop Window...
call .\node_modules\.bin\electron.cmd dist-electron\main.js
