@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -X utf8 -m graph_research connect
) else (
    echo Project environment not found. See 使用指南.md or docs/QUICKSTART.md.
    exit /b 1
)
pause
