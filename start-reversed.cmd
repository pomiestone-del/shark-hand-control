@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" hand_preview.py --port COM7 --reverse
) else (
  python hand_preview.py --port COM7 --reverse
)
if errorlevel 1 pause
