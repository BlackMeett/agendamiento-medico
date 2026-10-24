@echo off
cd /d "%~dp0"
start "Servidor Agendamiento Demo" cmd /k ".venv\Scripts\python.exe manage.py runserver"
timeout /t 3 /nobreak >nul
start "" "http://127.0.0.1:8000/cuenta/login/"
