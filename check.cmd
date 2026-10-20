@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -X utf8 tools\launch_checks.py %*
) else (
    python -X utf8 tools\launch_checks.py %*
)
exit /b %errorlevel%
