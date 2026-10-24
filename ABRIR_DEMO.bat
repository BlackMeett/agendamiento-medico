@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Preparar y abrir demo

echo ============================================
echo   Agendamiento medico - demo academica
echo ============================================
echo.

set "PY_CMD="
where py >nul 2>&1
if not errorlevel 1 (
    py -3.12 --version >nul 2>&1
    if not errorlevel 1 set "PY_CMD=py -3.12"
)
if not defined PY_CMD (
    where py >nul 2>&1
    if not errorlevel 1 (
        py --version >nul 2>&1
        if not errorlevel 1 set "PY_CMD=py"
    )
)
if not defined PY_CMD (
    where python >nul 2>&1
    if not errorlevel 1 set "PY_CMD=python"
)
if not defined PY_CMD (
    echo [ERROR] No se encontro Python.
    echo Instala Python 3.12 desde https://www.python.org/downloads/
    echo Marca la opcion "Add Python to PATH" durante la instalacion.
    echo.
    pause
    exit /b 1
)

set "NEED_INSTALL="
if not exist ".venv\Scripts\python.exe" (
    echo Creando entorno virtual...
    %PY_CMD% -m venv .venv
    if errorlevel 1 goto error
    set "NEED_INSTALL=1"
)

if not defined NEED_INSTALL (
    ".venv\Scripts\python.exe" -c "import django, tzdata" >nul 2>&1
    if errorlevel 1 set "NEED_INSTALL=1"
)

if defined NEED_INSTALL (
    echo Instalando dependencias. Esto puede tardar unos minutos...
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 goto error
)

echo Aplicando migraciones...
".venv\Scripts\python.exe" manage.py migrate --noinput
if errorlevel 1 goto error

echo Verificando datos de demostracion...
".venv\Scripts\python.exe" manage.py seed_demo --if-needed
if errorlevel 1 goto error

echo.
echo Iniciando servidor...
start "Servidor Agendamiento Demo" cmd /k ".venv\Scripts\python.exe manage.py runserver"
ping -n 5 127.0.0.1 >nul

echo Abriendo el navegador...
start "" "http://127.0.0.1:8000/cuenta/login/"

echo.
echo Listo. Si el navegador muestra un error, espera unos segundos y presiona F5.
echo No cierres la ventana "Servidor Agendamiento Demo" mientras uses la demo.
echo.
exit /b 0

:error
echo.
echo [ERROR] No se pudo preparar la demo.
echo Copia el mensaje de esta ventana y envialo para revisarlo.
echo.
pause
exit /b 1
