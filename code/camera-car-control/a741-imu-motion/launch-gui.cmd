@echo off
setlocal
cd /d "%~dp0"
if not exist "..\.venv\Scripts\pythonw.exe" (
    echo Project Python GUI environment is missing: ..\.venv\Scripts\pythonw.exe
    exit /b 1
)
if "%~1"=="--help" (
    "..\.venv\Scripts\python.exe" -X utf8 host\app.py --help
    exit /b
)
if not exist ".local\launcher" mkdir ".local\launcher"
start "EdgeMind A741" /B "..\.venv\Scripts\pythonw.exe" -X utf8 host\app.py %* >>".local\launcher\gui-stdout.log" 2>>".local\launcher\gui-stderr.log"
