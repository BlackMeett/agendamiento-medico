@echo off
setlocal
cd /d "%~dp0.."
if not exist ".deploy" mkdir ".deploy"
set PYTHONIOENCODING=utf-8
".\.venv\Scripts\python.exe" manage.py motor %* >> ".deploy\despachar.log" 2>&1
exit /b %ERRORLEVEL%
