# Sistema de agendamiento médico de segundo nivel

Demo académica de un sistema web para gestionar derivaciones, listas de espera, agendas, ofertas de hora, reagendamientos, portal de pacientes, notificaciones por portal y WhatsApp (simulado o Cloud API opcional), auditoría y reportes.

> **Advertencia:** es un prototipo académico con datos ficticios. No es un dispositivo médico, no está certificado, no acredita cumplimiento legal y no debe usarse con datos reales de pacientes.
>
> **¿Solo quieres abrir la demo?** Consulta la guía rápida [`COMO_ABRIR.md`](COMO_ABRIR.md).
>
> **¿Necesitas que otra persona entre desde internet?** Consulta [`README_PUBLICO.md`](README_PUBLICO.md).

**Ubicación del proyecto:** `C:\Users\Usuario\proyectos\agendamiento-medico`  
**Fecha de esta versión:** 24 de octubre de 2026

---

## 1. Inicio rápido en Windows

Requisitos: Windows 10/11 y Python 3.12 instalado. No se necesita Docker, PostgreSQL ni Git para ejecutar la demo.

> **Si el proyecto se descargó desde GitHub:** no incluye la carpeta `.venv` ni `db.sqlite3`. En Windows, ejecuta **`ABRIR_DEMO.bat`**: la primera vez crea el entorno, instala Django, aplica migraciones, carga los datos demo e inicia el servidor. Si usas macOS/Linux, revisa [`COMO_ABRIR.md`](COMO_ABRIR.md).

También puedes preparar todo manualmente. Abrir PowerShell y ejecutar:

```powershell
cd C:\Users\Usuario\proyectos\agendamiento-medico

py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_demo
.\.venv\Scripts\python.exe manage.py runserver
```

Abrir en el navegador:

- Panel interno: <http://127.0.0.1:8000/>
- Login: <http://127.0.0.1:8000/cuenta/login/>
- Portal de pacientes: <http://127.0.0.1:8000/portal/>
- Administración Django: <http://127.0.0.1:8000/admin/>

Si PowerShell bloquea la activación del entorno virtual, no es necesario activarlo: los comandos anteriores usan directamente `.\.venv\Scripts\python.exe`.

### Si ya existe una base de datos

`seed_demo` es mayormente idempotente, pero no reconstruye ofertas o citas históricas que ya fueron consumidas. Para dejar la demo en el estado inicial:

```powershell
Remove-Item -Force db.sqlite3
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_demo
```

---

## 2. Credenciales de demostración

Todas las cuentas usan la contraseña `Demo12345!`.

| Usuario | Rol | Uso principal |
|---|---|---|
| `admin@demo.cl` | Administrador / superusuario | Todo el panel, administración Django, auditoría. |
| `some@demo.cl` | SOME | Agendas, ofertas, listas, reportes, aprobar reagendamientos. |
| `admision@demo.cl` | Admisión / derivación | Pacientes, solicitudes, listas, reportes. |
| `medico@demo.cl` | Médico especialista | Datos clínicos, agendas, citas. |
| `paciente@demo.cl` | Paciente (Elena) | Portal, solicitud de hora por especialidad, ofertas, citas, preferencias, notificaciones. |

La autorización se valida en el servidor. Ocultar un botón en la interfaz no es la única defensa: las vistas comprueban rol y alcance por establecimiento (referencia del paciente, origen/destino de la solicitud y ofertas o citas en el establecimiento), y el portal comprueba que el paciente sea el propietario del dato.

---

## 3. Qué se puede probar

### Flujo interno

1. Entrar con `some@demo.cl`.
2. Revisar el panel, la lista de espera y las ofertas pendientes.
3. Aprobar o rechazar una propuesta de reagendamiento en **Reagendamientos**.
4. Suspender una agenda en **Agendas**. El sistema cancela ofertas pendientes, libera horas y genera propuestas para las citas afectadas cuando existe una alternativa compatible.
5. La tarea automática ejecuta el motor cada minuto para procesar eventos pendientes, vencer ofertas, asignar cupos, crear recordatorios y despachar notificaciones. También se puede ejecutar manualmente desde el panel. La bandeja **WhatsApp** permite revisar y enviar los mensajes manualmente.
6. Exportar el CSV de lista de espera y revisar **Reportes**.
7. Entrar con `admin@demo.cl` para revisar **Auditoría** y la administración Django.

### Flujo del paciente

1. Entrar con `paciente@demo.cl`.
2. En **Solicitar hora**, elegir una especialidad y uno de los dos modos:
   - **Asignación automática**: el sistema busca la primera hora compatible y genera una oferta inmediata; si no hay disponibilidad, la solicitud queda en lista de espera.
   - **Elegir hora**: el paciente ve las horas disponibles de la especialidad, selecciona una y el sistema revalida la disponibilidad antes de crear la cita confirmada.
3. En **Ofertas**, aceptar o rechazar la hora ofrecida en el modo automático. Aceptar crea una cita confirmada y ocupa la hora.
4. En **Mis horas**, cancelar una cita confirmada. La solicitud vuelve a lista de espera y el motor puede generar una nueva oferta si corresponde.
5. En **Mis datos**, actualizar contacto, canal preferido, consentimiento y preferencias de disponibilidad.
6. En **Notificaciones**, revisar mensajes del portal y marcarlos como leídos. Si el canal preferido es WhatsApp, también aparecen los mensajes externos, su estado y un enlace `wa.me` para revisar el texto.

En el modo manual, la reserva es directa: no se crea una oferta temporal. La solicitud queda `AGENDADA` y la hora pasa a `OCUPADA` después de revalidar especialidad, estado de la hora, citas activas y superposiciones del paciente.

### Visualizar datos clínicos

Entrar con `medico@demo.cl` y abrir una solicitud. Los datos clínicos están en una tabla separada y solo son accesibles para roles clínicos con alcance sobre la solicitud.

---

## 4. Comandos útiles

```powershell
# Verificación de configuración
.\.venv\Scripts\python.exe manage.py check

# Pruebas automatizadas de dominio, seguridad y flujos
.\.venv\Scripts\python.exe manage.py test -v 2

# Volver a cargar la semilla (sin borrar la base)
.\.venv\Scripts\python.exe manage.py seed_demo

# Ejecutar el motor completo y despachar el outbox
.\.venv\Scripts\python.exe manage.py motor

# Crear recordatorios de 24 h y despachar el outbox (manual)
.\.venv\Scripts\python.exe manage.py recordatorios

# Servidor local
.\.venv\Scripts\python.exe manage.py runserver
```

### WhatsApp

La demo funciona sin credenciales en modo **simulado**: el mensaje queda en el
outbox, se muestra en el portal y en **WhatsApp** del panel, y se ofrece un enlace
`wa.me` con el texto precargado. El enlace no envía solo: hay que presionar enviar
en WhatsApp y, si se quiere dejar constancia, usar **Registrar envío manual**.

Para envío automático se puede configurar WhatsApp Business Cloud API:

```powershell
$env:WHATSAPP_MODE = "CLOUD_API"
$env:WHATSAPP_CLOUD_API_TOKEN = "token-de-meta"
$env:WHATSAPP_PHONE_NUMBER_ID = "identificador-del-numero"
```

Meta puede exigir plantillas aprobadas y opt-in para mensajes iniciados por el
negocio. Revisa [`docs/WHATSAPP.md`](docs/WHATSAPP.md) antes de usar un número real.
No se implementa automatización no oficial de WhatsApp Web.

La suite actual contiene **59 pruebas** y cubre, entre otros temas:

- solicitud de hora desde el portal por especialidad;
- asignación automática y elección manual de una hora disponible;
- reserva manual directa con revalidación y creación de cita confirmada;
- prioridad por antigüedad;
- aceptación y rechazo de ofertas;
- vencimiento y liberación de horas;
- prevención de doble reserva, superposiciones y ofertas duplicadas;
- suspensión de agenda y generación de propuestas;
- aprobación y fallo persistente de una propuesta;
- registro de atención e inasistencia sin sanción automática;
- notificaciones simuladas y outbox;
- WhatsApp simulado, enlace `wa.me` y envío Cloud API con respuesta simulada;
- reintentos, fallo con alerta y registro de envío manual;
- recordatorios de 24 h idempotentes;
- notificaciones de rechazo, cancelación y reagendamiento;
- auditoría append-only;
- aislamiento de pacientes y establecimientos;
- restricciones de rol para agendas y pacientes;
- filtrado de formularios por establecimiento.

---

## 5. Arquitectura implementada

Monolito Django con aplicaciones separadas por responsabilidad:

```text
config/       Configuración del proyecto y rutas raíz
core/         Auditoría, alertas, parámetros, outbox, panel, reportes, CSV
accounts/     Perfil de usuario, roles y decoradores de acceso
gestion/      Modelos, servicios de dominio, vistas y formularios operativos
portal/       Portal del paciente y aislamiento por propietario
templates/    Plantillas Django
static/       CSS propio, sin CDN
docs/         Análisis, diseño y decisiones
```

### Decisiones de implementación

- **Django 5.2.18 + SQLite** para que la demo funcione en el entorno disponible sin Docker/PostgreSQL.
- **Plantillas Django + CSS propio**, sin SPA ni dependencia de CDN, para reducir instalación y puntos de fallo.
- **Servicios de dominio** en `gestion/services.py`; las vistas no implementan reglas críticas por su cuenta.
- **Oferta como reserva temporal**, no como cita: al aceptar se revalida la hora y se crea la cita.
- **Reserva manual directa desde el portal**: el paciente elige una hora concreta y el servicio revalida disponibilidad, especialidad, citas activas y superposiciones antes de crear la cita; no se crea una oferta temporal.
- **Outbox transaccional** para notificaciones, con `dedupe_key` para evitar duplicados y un adaptador de WhatsApp desacoplado (`core/whatsapp.py`).
- **Auditoría append-only** en `core.EventoAuditoria`; no se permite editar ni borrar desde la aplicación.
- **Restricciones de base de datos** para oferta pendiente única por solicitud y hora, y cita activa única por solicitud y por hora.
- **CSRF, autenticación de sesión y hash de contraseñas** de Django.
- **CSV con escape de fórmulas** para reducir inyección de fórmulas al abrir en una hoja de cálculo.

La Etapa 1 proponía PostgreSQL, HTMX y Tailwind. Por las restricciones del entorno y el tiempo disponible, la implementación usa SQLite y plantillas/CSS propio. La separación modular, los servicios de dominio y las pruebas se mantuvieron. La recomendación de PostgreSQL para producción sigue vigente.

---

## 6. Reglas y parámetros de la demo

- Vigencia de una oferta: **48 horas** (`Parametro: oferta.vigencia_horas`).
- Duración de consulta por defecto: **30 minutos**.
- No se aplica sanción automática por inasistencia.
- No se inventan prioridades clínicas ni puntajes médicos.
- La prioridad de la cola usa antigüedad y preferencias declaradas, no criterios clínicos.
- Una oferta vencida libera la hora y genera un evento para ofrecerla a la siguiente persona.
- Suspender una agenda no borra citas: las marca como `REAGENDAMIENTO_PENDIENTE` y crea una propuesta si encuentra una alternativa.
- Aprobar una propuesta es una decisión humana; no se aprueba automáticamente.
- El motor no corre en segundo plano: se ejecuta desde el panel o mediante una tarea programada que se implementaría en producción.

---

## 7. Datos de demostración

La semilla crea datos ficticios:

- establecimientos, especialidades y profesionales de ejemplo;
- **una sola ficha de paciente: Elena Demo Rojas**, vinculada a `paciente@demo.cl`, con canal preferido WhatsApp y un teléfono ficticio;
- agendas publicadas con horas disponibles en varias especialidades;
- sin solicitudes, ofertas ni citas iniciales, para probar el flujo desde cero;
- alertas operativas de demostración.

El paciente puede crear su primera solicitud desde **Solicitar hora**, ya sea con asignación automática o eligiendo una hora disponible. En el modo automático recibe una oferta si hay disponibilidad; en el modo manual la cita queda confirmada después de la revalidación. Los documentos, nombres, correos y teléfonos son ficticios. No usar datos reales.

---

## 8. Limitaciones honestas

### Concurrencia y base de datos

- SQLite no ofrece el mismo comportamiento de bloqueo que PostgreSQL; `select_for_update` es esencialmente un no-op.
- La sección crítica se protege con un `RLock` de proceso y restricciones únicas, suficiente para la demo de un solo proceso.
- **No se demostró concurrencia real entre múltiples procesos.** Antes de producción se requiere PostgreSQL, pruebas de carga y pruebas de doble reserva con procesos/transacciones concurrentes.

### Notificaciones

- Por defecto, WhatsApp, correo y SMS son simulados: los mensajes externos quedan como `SIMULADO` y no salen de la máquina.
- WhatsApp puede usar Cloud API de Meta si se configuran `WHATSAPP_MODE=CLOUD_API` y las credenciales. No se incluyen credenciales reales.
- El enlace `wa.me` abre un chat con el texto precargado, pero no envía automáticamente; el envío manual se puede registrar en la bandeja interna.
- No hay worker interno: la demo usa una tarea externa de Windows que ejecuta `manage.py motor` cada minuto. Para producción se requiere un worker o planificador 24/7.
- No se implementan webhooks de entrega/lectura, respuestas entrantes, gestión de plantillas ni campañas masivas.
- Los mensajes del portal quedan pendientes hasta que el paciente los lee.

### Alcance funcional

- No hay integración con sistemas de salud, HL7/FHIR, licencias, facturación ni ficha clínica institucional.
- No hay calendario de feriados, vacaciones, licencias médicas reales ni reglas locales de agendas.
- No hay activación de cuentas por código, recuperación de contraseña ni segundo factor.
- No hay pantalla de funcionario para crear una oferta manual; el paciente puede elegir una hora desde el portal y el flujo automático sigue siendo el principal para la lista de espera.
- No hay doble aprobación de reagendamientos: un usuario con permiso puede aprobar.
- No se implementan prioridades clínicas, plazos legales, sanciones ni garantías de atención.
- No hay aplicación móvil ni API pública.

### Producción

Esta demo **no está lista para producción**. Antes de un piloto real se necesita, como mínimo:

1. PostgreSQL y migraciones revisadas para el entorno institucional.
2. `DEBUG=0`, `DJANGO_SECRET_KEY` segura y `ALLOWED_HOSTS` configurado.
3. HTTPS, cookies seguras, protección contra fuerza bruta y segundo factor para administración.
4. Copias de respaldo, restauración probada y política de retención.
5. Proveedor real de notificaciones con consentimiento, rebotes y bajas.
6. Worker o scheduler para outbox y vencimiento de ofertas.
7. Pruebas de concurrencia multiproceso y de carga.
8. Revisión legal y de seguridad institucional; análisis de riesgos y protección de datos.
9. Auditoría externa, observabilidad, alertas y soporte.
10. Validación clínica y operativa con las personas usuarias.

---

## 9. Documentación

- [Etapa 1: análisis y diseño](docs/etapa-1/README.md)
- [Resumen de requisitos](docs/etapa-1/00-resumen-requisitos.md)
- [Arquitectura](docs/etapa-1/01-arquitectura.md)
- [Flujos y concurrencia](docs/etapa-1/02-flujos-concurrencia.md)
- [Modelo de datos](docs/etapa-1/03-modelo-datos.md)
- [Seguridad y permisos](docs/etapa-1/04-seguridad-permisos.md)
- [Historias, pruebas y UX](docs/etapa-1/05-historias-pruebas-ux.md)
- [Plan, riesgos y decisiones](docs/etapa-1/06-plan-riesgos-decisiones.md)
- [Notas de implementación](docs/etapa-2/README.md)
- [WhatsApp: modos, eventos y límites](docs/WHATSAPP.md)

---

## 10. Estructura resumida

```text
manage.py
requirements.txt
.env.example
db.sqlite3                  # se crea localmente; no versionar
config/
core/
accounts/
gestion/
portal/
templates/
static/
docs/
```

La base `db.sqlite3` es local y desechable. Para volver al estado de demostración, seguir las instrucciones de reinicio de la sección 1.
