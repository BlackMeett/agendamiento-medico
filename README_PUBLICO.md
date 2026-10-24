# Publicar la demo en internet (gratis)

Esta configuración expone la demo con **Cloudflare Quick Tunnel**: no hay que abrir
puertos en el router, no se expone la IP pública y no hace falta cuenta ni tarjeta.

## URL actual

```text
https://headquarters-basis-orleans-correctly.trycloudflare.com
```

Login: <https://headquarters-basis-orleans-correctly.trycloudflare.com/cuenta/login/>

La URL se guarda en `.deploy\url_publica.txt`. **Cambia cada vez que se reinicia el
túnel** (por ejemplo, al reiniciar el PC). Para abrir la URL vigente, doble clic en
`ABRIR_URL_PUBLICA.bat`.

## Instalar cloudflared (solo la primera vez)

En PowerShell:

```powershell
$dir = "$env:LOCALAPPDATA\cloudflared"
New-Item -ItemType Directory -Force -Path $dir | Out-Null
Invoke-WebRequest `
  -Uri "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe" `
  -OutFile "$dir\cloudflared.exe"
```

## Cómo funciona

- Django corre con **waitress** en `127.0.0.1:8001` (solo local).
- **cloudflared** abre una conexión saliente y publica ese puerto en HTTPS.
- Los archivos estáticos los sirve **WhiteNoise** (no `runserver`).
- La configuración está en `config/settings_public.py`; **no modifica** tu
  `config/settings.py` ni el servidor local del puerto 8000.

## Arrancar y detener

| Acción | Cómo |
|---|---|
| Arrancar | Doble clic en `ABRIR_PUBLICO.bat` |
| Detener | `powershell -ExecutionPolicy Bypass -File .\detener_publico.ps1` |
| Ver URL vigente | `ABRIR_URL_PUBLICA.bat` |
| Arranque automático | Ya está en la carpeta Inicio de Windows (`AgendamientoDemoPublico.vbs`) |

El arranque automático se ejecuta al **iniciar sesión** en Windows. Si el PC se
reinicia, se genera una URL nueva.

## Cuentas demo

Contraseña para todas: `Demo12345!`

| Correo | Perfil |
|---|---|
| `admin@demo.cl` | Administrador |
| `some@demo.cl` | SOME |
| `admision@demo.cl` | Admisión |
| `medico@demo.cl` | Médico |
| `paciente@demo.cl` | Paciente |

## Limitaciones importantes

- **Es una demo con datos ficticios.** No cargues datos reales de pacientes.
- El usuario administrador y sus credenciales son públicos (es parte de la demo).
- El PC debe quedar **encendido y con sesión iniciada**. Ya se desactivó la
  suspensión automática con corriente alterna.
- Quick Tunnel es gratis pero **sin SLA** y con URL temporal. Para algo serio,
  usa un dominio propio + túnel con nombre de Cloudflare.
- El puerto 8001 escucha solo en `127.0.0.1`; no está abierto a tu red local.
- WhatsApp está en **modo simulado** por defecto: no sale ningún mensaje a Meta.
  Para envío automático configura `WHATSAPP_MODE=CLOUD_API` y las credenciales
  antes de reiniciar la publicación. Revisa [`docs/WHATSAPP.md`](docs/WHATSAPP.md).

## Si el login público muestra error 403

La página puede cargar, pero el POST del login falla si Django no confía en el
dominio del túnel. La configuración ya incluye:

```python
CSRF_TRUSTED_ORIGINS = ["https://*.trycloudflare.com"]
```

Si cambias a otro proveedor de túnel, agrega su dominio en
`config/settings_public.py` y reinicia la publicación.

## Si quieres una URL fija gratis

Cloudflare Quick Tunnel no permite elegir el subdominio. Las opciones gratuitas
con URL estable requieren una cuenta gratuita:

### Tailscale Funnel (recomendado)

```powershell
winget install --id Tailscale.Tailscale -e
tailscale up
tailscale funnel --bg 8001
tailscale funnel status
```

Da una URL fija tipo `https://tu-equipo.tu-tailnet.ts.net`. Requiere permisos de
administrador para instalar el cliente y una cuenta gratuita de Tailscale.

### ngrok con dominio estático

Crea una cuenta gratuita en ngrok, copia tu `authtoken` y ejecuta:

```powershell
ngrok config add-authtoken <TOKEN>
ngrok http --url=tu-subdominio.ngrok-free.app 8001
```

Ngrok free incluye un dominio estático por cuenta, pero muestra una página de
advertencia a los visitantes.
