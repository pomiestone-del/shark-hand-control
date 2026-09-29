@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" hand_preview.py --port COM7
) else (
  python hand_preview.py --port COM7
)
if errorlevel 1 pause
