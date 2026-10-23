@echo off
setlocal
cd /d "%~dp0"
if not exist "..\.venv\Scripts\python.exe" (
    echo Project Python environment is missing: ..\.venv\Scripts\python.exe
    pause
    exit /b 1
)
"..\.venv\Scripts\python.exe" -X utf8 host\app.py %*
if errorlevel 1 (
    echo GUI startup failed. Check the error above.
    echo To install dependencies, run: ..\.venv\Scripts\python.exe -m pip install -r ..\requirements.txt
    pause
    exit /b 1
)
