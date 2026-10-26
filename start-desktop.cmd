@echo off
setlocal DisableDelayedExpansion
cd /d "%~dp0"
if errorlevel 1 goto directory_error
if not exist "%~dp0.venv\Scripts\pythonw.exe" goto missing_environment
if not exist "%~dp0tools\desktop_entry.py" goto missing_entry
start "" /b "%~dp0.venv\Scripts\pythonw.exe" -X utf8 "%~dp0tools\desktop_entry.py"
if errorlevel 1 goto launch_error
exit /b 0

:directory_error
echo Could not open the project directory.
goto failed

:missing_environment
echo Project Python environment not found. See README.md or docs\QUICKSTART.md.
goto failed

:missing_entry
echo Desktop entry was not found. Keep this launcher in the project directory.
goto failed

:launch_error
echo Desktop could not start. Check outputs\desktop\startup.log.

:failed
pause
exit /b 1
