# Publica la demo con un túnel gratuito de Cloudflare (sin cuenta, sin abrir puertos).
# Uso: powershell -NoProfile -ExecutionPolicy Bypass -File .\host_publico.ps1
$ErrorActionPreference = "Stop"

$Project = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Project

$Deploy = Join-Path $Project ".deploy"
New-Item -ItemType Directory -Force -Path $Deploy | Out-Null

# Clave de Django persistente entre reinicios (para no cerrar sesiones).
$KeyFile = Join-Path $Deploy "secret.key"
if (-not (Test-Path $KeyFile)) {
    $bytes = New-Object byte[] 48
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    [Convert]::ToBase64String($bytes) | Set-Content -Encoding ASCII $KeyFile
}

$env:DJANGO_SETTINGS_MODULE = "config.settings_public"
$env:DJANGO_DEBUG = "0"
$env:DJANGO_ALLOWED_HOSTS = "*"
$env:DJANGO_SECRET_KEY = (Get-Content $KeyFile -Raw).Trim()
$env:DEMO_MODE = "1"

# Detener instancias anteriores de esta publicación (no toca el runserver del 8000).
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match "127\.0\.0\.1:8001" -and $_.CommandLine -match "waitress|cloudflared" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 1

$Python = Join-Path $Project ".venv\Scripts\python.exe"
$Waitress = Join-Path $Project ".venv\Scripts\waitress-serve.exe"
$Cloudflared = Join-Path $env:LOCALAPPDATA "cloudflared\cloudflared.exe"

if (-not (Test-Path $Python)) {
    throw "Falta .venv. Ejecuta primero ABRIR_DEMO.bat."
}
if (-not (Test-Path $Waitress)) {
    throw "Falta waitress. Ejecuta: .venv\Scripts\python.exe -m pip install -r requirements.txt"
}
if (-not (Test-Path $Cloudflared)) {
    throw "Falta cloudflared en $Cloudflared. Sigue las instrucciones de README_PUBLICO.md"
}

Write-Host "Actualizando base de datos y archivos estaticos..."
& $Python manage.py migrate --noinput
if ($LASTEXITCODE -ne 0) { throw "Fallo manage.py migrate." }
& $Python manage.py seed_demo --if-needed
if ($LASTEXITCODE -ne 0) { throw "Fallo manage.py seed_demo." }
& $Python manage.py collectstatic --noinput | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Fallo manage.py collectstatic." }

# 1) Servidor WSGI en local, solo accesible desde el túnel.
Start-Process -FilePath $Waitress `
    -ArgumentList "--listen=127.0.0.1:8001", "config.wsgi:application" `
    -WorkingDirectory $Project `
    -RedirectStandardOutput (Join-Path $Deploy "waitress.log") `
    -RedirectStandardError (Join-Path $Deploy "waitress.err.log") `
    -WindowStyle Hidden

# 2) Túnel HTTPS gratuito (URL aleatoria *.trycloudflare.com).

$TunnelLog = Join-Path $Deploy "cloudflared.log"
if (Test-Path $TunnelLog) { Remove-Item $TunnelLog -Force }

Start-Process -FilePath $Cloudflared `
    -ArgumentList "tunnel", "--url", "http://127.0.0.1:8001", "--no-autoupdate" `
    -WorkingDirectory $Project `
    -RedirectStandardOutput (Join-Path $Deploy "cloudflared.out.log") `
    -RedirectStandardError $TunnelLog `
    -WindowStyle Hidden

# 3) Esperar a que el túnel publique la URL.
$Url = $null
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Seconds 1
    if (Test-Path $TunnelLog) {
        $match = [regex]::Match((Get-Content $TunnelLog -Raw -ErrorAction SilentlyContinue), "https://[a-z0-9-]+\.trycloudflare\.com")
        if ($match.Success) { $Url = $match.Value; break }
    }
}

if (-not $Url) {
    Write-Host "No se pudo obtener la URL pública. Revisa $TunnelLog" -ForegroundColor Red
    exit 1
}

$Url | Set-Content -Encoding ASCII (Join-Path $Deploy "url_publica.txt")

Write-Host ""
Write-Host "  Demo publicada:  $Url" -ForegroundColor Green
Write-Host "  Login:           $Url/cuenta/login/" -ForegroundColor Green
Write-Host ""
Write-Host "  La URL cambia si reinicias el túnel." -ForegroundColor Yellow
Write-Host "  Para detenerla:  .\detener_publico.ps1" -ForegroundColor Yellow
Write-Host ""
