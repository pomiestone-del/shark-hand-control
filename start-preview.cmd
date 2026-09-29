@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" hand_preview.py --preview
) else (
  python hand_preview.py --preview
)
if errorlevel 1 pause
