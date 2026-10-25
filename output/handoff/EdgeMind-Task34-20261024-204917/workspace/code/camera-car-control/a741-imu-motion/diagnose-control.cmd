@echo off
setlocal
cd /d "%~dp0"
if not exist "..\.venv\Scripts\python.exe" (
    echo Project Python environment is missing.
    pause
    exit /b 1
)
"..\.venv\Scripts\python.exe" -X utf8 scripts\diagnose_control.py %*
pause
