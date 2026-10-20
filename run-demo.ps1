$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot '.venv\Scripts\python.exe') -X utf8 (Join-Path $PSScriptRoot 'assistant.py') @args
exit $LASTEXITCODE
