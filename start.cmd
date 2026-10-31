@echo off
cd /d "%~dp0"
if not exist ".conda\pythonw.exe" (
  echo Please run setup.ps1 first.
  pause
  exit /b 1
)
start "" "%~dp0.conda\pythonw.exe" "%~dp0main.py"
