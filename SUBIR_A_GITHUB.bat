@echo off
setlocal
cd /d "%~dp0"

set "GIT=C:\Program Files\Git\cmd\git.exe"
set "GH=C:\Program Files\GitHub CLI\gh.exe"

if not exist "%GIT%" (
    echo No se encontro Git. Instala Git for Windows y vuelve a intentar.
    pause
    exit /b 1
)

if not exist "%GH%" (
    echo No se encontro GitHub CLI. Instala GitHub CLI y vuelve a intentar.
    pause
    exit /b 1
)

"%GH%" auth status >nul 2>&1
if errorlevel 1 (
    echo.
    echo Inicia sesion en GitHub. Se abrira el navegador.
    echo Completa la autorizacion y vuelve a esta ventana.
    echo.
    "%GH%" auth login --hostname github.com --git-protocol https --web
    if errorlevel 1 (
        echo.
        echo No se pudo iniciar sesion en GitHub.
        pause
        exit /b 1
    )
)

for /f "delims=" %%u in ('"%GH%" api user --jq .login') do set "GHUSER=%%u"
if "%GHUSER%"=="" (
    echo.
    echo No se pudo obtener el usuario de GitHub.
    pause
    exit /b 1
)

"%GIT%" config user.name "%GHUSER%"
"%GIT%" config user.email "%GHUSER%@users.noreply.github.com"

"%GIT%" add .
"%GIT%" diff --cached --quiet
if errorlevel 1 (
    "%GIT%" commit -m "Demo funcional de agendamiento medico"
) else (
    echo No hay cambios nuevos para confirmar.
)

"%GIT%" remote get-url origin >nul 2>&1
if errorlevel 1 (
    echo.
    echo Creando repositorio privado en GitHub...
    "%GH%" repo create agendamiento-medico --private --source=. --remote=origin --push
) else (
    echo.
    echo El repositorio remoto ya esta configurado. Subiendo cambios...
    "%GIT%" push -u origin main
)

if errorlevel 1 (
    echo.
    echo No se pudo crear o subir el repositorio.
    echo Revisa si ya existe un repositorio con ese nombre en tu cuenta.
    echo Tambien puedes revisar https://github.com/%GHUSER%
) else (
    echo.
    echo Listo. Repositorio: https://github.com/%GHUSER%/agendamiento-medico
)

pause
