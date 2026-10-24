@echo off
title Agendamiento Demo - Publico
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0host_publico.ps1"
echo.
pause
