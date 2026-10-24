# Cómo abrir la demo

Guía rápida para ejecutar el sistema de agendamiento médico en otro computador.

> **Importante:** el repositorio de GitHub no incluye la carpeta `.venv` ni la base de datos `db.sqlite3`. La primera ejecución de `ABRIR_DEMO.bat` crea el entorno, aplica las migraciones y carga los datos ficticios automáticamente.

---

## Requisitos

- Windows 10/11.
- Python 3.12 o compatible instalado.
- Conexión a internet la primera vez, para descargar Django.
- Si descargaste un ZIP desde GitHub, **descomprímelo antes de ejecutar**. No ejecutes los archivos dentro del ZIP.

---

## Opción 1: Windows, doble clic

1. Descomprime o clona el proyecto en una carpeta normal, por ejemplo:
   ```text
   C:\demo\agendamiento-medico
   ```
2. Abre esa carpeta.
3. Haz doble clic en **`ABRIR_DEMO.bat`**.
4. La primera vez puede tardar unos minutos. La ventana mostrará:
   - creación del entorno `.venv`;
   - instalación de Django;
   - migraciones de la base;
   - carga de datos demo;
   - inicio del servidor.
5. Se abrirá el navegador en:
   ```text
   http://127.0.0.1:8000/cuenta/login/
   ```
6. Deja abierta la ventana negra llamada **Servidor Agendamiento Demo**. Si la cierras, la página dejará de funcionar.

Si el navegador muestra un error porque el servidor todavía está iniciando, espera unos segundos y presiona `F5`.

---

## Opción 2: Windows, manual desde PowerShell

Abre PowerShell y ejecuta, cambiando la ruta por la carpeta real donde está el proyecto:

```powershell
cd C:\demo\agendamiento-medico

py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_demo
.\.venv\Scripts\python.exe manage.py runserver
```

Cuando aparezca:

```text
Starting development server at http://127.0.0.1:8000/
```

abre:

```text
http://127.0.0.1:8000/cuenta/login/
```

> La consola debe permanecer abierta mientras uses la demo. Para detener el servidor, presiona `Ctrl + C`.

---

## Opción 3: macOS o Linux

El archivo `.bat` es solo para Windows. En macOS/Linux usa:

```bash
cd /ruta/donde/esta/agendamiento-medico

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Luego abre `http://127.0.0.1:8000/cuenta/login/`.

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
| `paciente@demo.cl` | Paciente (Elena) | Portal, solicitud de hora automática o manual, ofertas, horas y perfil |

La demo tiene una sola ficha de paciente: **Elena Demo Rojas**.

---

## Rutas principales

| Pantalla | Dirección |
|---|---|
| Login | <http://127.0.0.1:8000/cuenta/login/> |
| Panel interno | <http://127.0.0.1:8000/panel/> |
| Portal del paciente | <http://127.0.0.1:8000/portal/> |
| Solicitar hora | <http://127.0.0.1:8000/portal/solicitar/> |
| Administración Django | <http://127.0.0.1:8000/admin/> |
| Estado del servidor | <http://127.0.0.1:8000/health/> |

En **Solicitar hora** puedes elegir una especialidad y uno de estos modos:

- **Asignación automática:** si hay una hora compatible, aparece una oferta para aceptar; si no, la solicitud queda en lista de espera.
- **Elegir una hora disponible:** se muestran las horas de la especialidad agrupadas por día. Al seleccionar una y confirmar, el sistema revalida la disponibilidad y crea la cita directamente.

En el modo manual no se crea una oferta temporal: la cita queda confirmada y la hora pasa a ocupada. Si no hay horas para elegir, aparece un aviso y puedes cambiar a asignación automática antes de enviar.

---

## Probar WhatsApp

La demo viene con WhatsApp en **modo simulado**: no envía mensajes reales ni pide
credenciales. Para verlo:

1. Entra como paciente y revisa **Notificaciones** después de solicitar o aceptar una hora.
2. Entra como `some@demo.cl` y abre **WhatsApp** en el menú lateral.
3. Presiona **Despachar pendientes**. Los mensajes quedarán como **Simulado**.
4. Presiona **Abrir WhatsApp** para abrir un chat con el texto precargado. El enlace
   no envía solo; debes presionar enviar en WhatsApp.
5. Si lo enviaste manualmente, usa **Registrar envío manual** para dejar constancia.

Elena Demo tiene un teléfono ficticio. Para probar con tu propio número, cámbialo
en **Mis datos** y usa código de país, por ejemplo `+56 9 ...`.

El envío automático real es opcional y requiere configurar WhatsApp Business Cloud
API de Meta (token, identificador de número y destinatario autorizado). Los pasos,
variables y límites están en [`docs/WHATSAPP.md`](docs/WHATSAPP.md).

---

## Si llega al login pero no entra

Esto casi siempre significa que falta cargar la base de datos demo. El repositorio no incluye `db.sqlite3`.

### 1. Verifica que el servidor esté activo

La ventana **Servidor Agendamiento Demo** debe mostrar algo similar a:

```text
Starting development server at http://127.0.0.1:8000/
```

Si esa ventana se cerró, vuelve a ejecutar `ABRIR_DEMO.bat`.

### 2. Carga las cuentas demo manualmente

Desde PowerShell, en la carpeta del proyecto:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_demo
```

Luego vuelve a intentar el login con `paciente@demo.cl` / `Demo12345!`.

También puedes ejecutar `ABRIR_DEMO.bat` otra vez: ahora verifica automáticamente si faltan los datos demo.

### 3. Revisa el mensaje de la consola

Si aparece un error en la ventana negra, cópialo completo y envíalo. Los errores más comunes son:

- `No se encontro Python`: instalar Python y marcar **Add Python to PATH**.
- `No module named django`: ejecutar de nuevo `ABRIR_DEMO.bat` con internet, o instalar dependencias:
  ```powershell
  .\.venv\Scripts\python.exe -m pip install -r requirements.txt
  ```
- `no such table`: faltan las migraciones:
  ```powershell
  .\.venv\Scripts\python.exe manage.py migrate
  .\.venv\Scripts\python.exe manage.py seed_demo
  ```

### 4. El puerto 8000 está ocupado

Ejecuta el servidor en otro puerto:

```powershell
.\.venv\Scripts\python.exe manage.py runserver 8001
```

Y abre:

```text
http://127.0.0.1:8001/cuenta/login/
```

---

## Reiniciar los datos demo

Esto elimina la base local y vuelve a cargar los datos ficticios iniciales:

```powershell
Remove-Item -Force db.sqlite3
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_demo
```

Después inicia el servidor con `ABRIR_DEMO.bat` o con `manage.py runserver`.

---

## Importante

Esta es una demo académica con datos ficticios. Por defecto las notificaciones externas son simuladas; WhatsApp puede configurarse con Cloud API, pero la demo no es un sistema clínico certificado ni está lista para producción. No uses datos reales de pacientes.

Para más detalles técnicos, consulta:

- [`README.md`](README.md)
- [`docs/etapa-2/README.md`](docs/etapa-2/README.md)
