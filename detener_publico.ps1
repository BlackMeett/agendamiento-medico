# Detiene el servidor y el túnel de la publicación (no toca el runserver local del 8000).
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match "127\.0\.0\.1:8001" -and $_.CommandLine -match "waitress|cloudflared" } |
    ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        Write-Host "Detenido PID $($_.ProcessId)"
    }
Write-Host "Publicación detenida."
