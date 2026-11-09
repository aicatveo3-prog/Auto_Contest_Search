@echo off
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python not found. Install from https://www.python.org/downloads/
  pause
  exit /b 1
)

start "" pyw "%~dp0launcher.py"
