# Cómo abrir la demo

Guía rápida para abrir el sistema de agendamiento médico en Windows.

**Carpeta del proyecto:**

```text
C:\Users\Usuario\proyectos\agendamiento-medico
```

La base de datos demo ya está creada y cargada con datos ficticios. Solo necesitas iniciar el servidor.

---

## Opción 1: doble clic

1. Abre la carpeta del proyecto.
2. Haz doble clic en **`ABRIR_DEMO.bat`**.
3. Espera unos segundos.
4. Se abrirá el navegador en la pantalla de login:

```text
http://127.0.0.1:8000/cuenta/login/
```

Si el navegador muestra un error porque el servidor aún está iniciando, espera unos segundos y actualiza la página con `F5`.

---

## Opción 2: desde PowerShell

Abre PowerShell y ejecuta:

```powershell
cd C:\Users\Usuario\proyectos\agendamiento-medico
.\.venv\Scripts\python.exe manage.py runserver
```

Cuando aparezca un mensaje similar a:

```text
Starting development server at http://127.0.0.1:8000/
```

abre el navegador en:

```text
http://127.0.0.1:8000/cuenta/login/
```

> La consola debe permanecer abierta mientras uses la demo. Para detener el servidor, presiona `Ctrl + C` en esa consola.

---

## Cuentas de prueba

Todas usan la contraseña:

```text
Demo12345!
```

| Correo | Perfil | Para probar |
|---|---|---|
| `admin@demo.cl` | Administrador | Todo el panel, auditoría y administración Django |
| `some@demo.cl` | SOME | Agendas, ofertas, reportes y reagendamientos |
| `admision@demo.cl` | Admisión | Pacientes, solicitudes y listas de espera |
| `medico@demo.cl` | Médico | Datos clínicos, agendas y citas |
| `paciente@demo.cl` | Paciente | Portal, ofertas, horas y perfil |

---

## Rutas principales

| Pantalla | Dirección |
|---|---|
| Login | <http://127.0.0.1:8000/cuenta/login/> |
| Panel interno | <http://127.0.0.1:8000/panel/> |
| Portal del paciente | <http://127.0.0.1:8000/portal/> |
| Administración Django | <http://127.0.0.1:8000/admin/> |
| Estado del servidor | <http://127.0.0.1:8000/health/> |

Para entrar al portal del paciente, inicia sesión con `paciente@demo.cl`.

---

## Si algo no funciona

### El navegador no conecta

Verifica que la consola siga abierta y muestre el servidor iniciado. Luego actualiza con `F5`.

### El puerto 8000 está ocupado

Ejecuta el servidor en otro puerto:

```powershell
.\.venv\Scripts\python.exe manage.py runserver 8001
```

Y abre:

```text
http://127.0.0.1:8001/cuenta/login/
```

### `ABRIR_DEMO.bat` no funciona

Usa la opción de PowerShell. El archivo `.bat` solo automatiza la apertura del servidor y del navegador.

### Quiero reiniciar los datos demo

Desde PowerShell, en la carpeta del proyecto:

```powershell
Remove-Item -Force db.sqlite3
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_demo
.\.venv\Scripts\python.exe manage.py runserver
```

Esto elimina la base local y vuelve a cargar los datos ficticios iniciales.

---

## Importante

Esta es una demo académica con datos ficticios y notificaciones simuladas. No uses datos reales de pacientes. No es un sistema clínico certificado ni está listo para producción.

Para más detalles técnicos, consulta:

- [`README.md`](README.md)
- [`docs/etapa-2/README.md`](docs/etapa-2/README.md)
