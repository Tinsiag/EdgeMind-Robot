@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" host\app.py %*
) else (
    python host\app.py %*
)
if errorlevel 1 pause
