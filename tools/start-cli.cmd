@echo off
setlocal DisableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0.." || exit /b 1
if not exist ".venv\Scripts\python.exe" (
    echo Project environment not found. See 使用指南.md or docs/QUICKSTART.md.
    exit /b 1
)
".venv\Scripts\python.exe" -X utf8 -m graph_research "%~1"
pause
