@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" -X utf8 "tools\desktop_entry.py"
) else (
    echo 请先安装桌面版依赖，参见 DESKTOP_APP.md。
    pause
)
