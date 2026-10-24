@echo off
cd /d "%~dp0"
if not exist ".deploy\url_publica.txt" (
  echo No hay URL publica. Ejecuta ABRIR_PUBLICO.bat primero.
  pause
  exit /b 1
)
set /p URL=<".deploy\url_publica.txt"
start "" "%URL%"
