@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" -X utf8 "tools\desktop_entry.py"
) else (
    echo 请先按 使用指南.md 的“安装到新电脑”步骤安装Python及项目依赖。
    pause
)
