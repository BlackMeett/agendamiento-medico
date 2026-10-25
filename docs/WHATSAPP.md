# WhatsApp y correo en la demo

La demo usa el mismo outbox transaccional para el portal y los canales externos.
WhatsApp tiene dos modos:

| Modo | Qué hace | Credenciales |
|---|---|---|
| `SIMULADO` (por defecto) | Registra el mensaje, lo muestra en el portal y en la bandeja interna, y genera un enlace `wa.me` con el texto precargado. No contacta a Meta. | No requiere |
| `CLOUD_API` | Intenta enviar automáticamente con WhatsApp Business Cloud API de Meta. | Token, identificador del número emisor y destinatario con código de país |

No se implementa automatización de WhatsApp Web ni de clientes no oficiales. Esas
prácticas pueden incumplir los términos del servicio, exponer la sesión y fallar
sin aviso.

## Eventos cubiertos

El paciente recibe un mensaje en el portal y, si su canal preferido es WhatsApp
o correo electrónico y tiene contacto/consentimiento, también se encola el
mensaje externo:

1. Nueva oferta de hora.
2. Cita confirmada (oferta aceptada o reserva manual).
3. Cancelación de una cita o de una oferta por cambio de agenda.
4. Reagendamiento: aviso cuando la hora entra en revisión y aviso cuando se
   aprueba, además del aviso de cancelación si la propuesta se rechaza.
5. Rechazo de una solicitud inicial, con el motivo.
6. Recordatorio de 24 horas antes de una cita confirmada.

## Probar el modo simulado

1. Entrar al portal con `paciente@demo.cl` / `Demo12345!`.
2. En **Mis datos**, confirmar que el canal preferido es **WhatsApp** y que el
   teléfono tiene código de país. Elena Demo trae un teléfono ficticio; para una
   prueba con un número real, cámbialo ahí mismo.
3. Crear una solicitud desde **Solicitar hora**, aceptar una oferta o reservar
   una hora.
4. Con `some@demo.cl`, abrir **WhatsApp** en el menú lateral.
5. Revisar la cola y presionar **Despachar pendientes**. En modo simulado los
   mensajes quedan como `SIMULADO`, no como `ENVIADO`.
6. Presionar **Abrir WhatsApp** para abrir el chat con el texto precargado.
   Después de enviarlo desde WhatsApp, se puede usar **Registrar envío manual**
   para dejar constancia en la demo.

El enlace `wa.me` solo abre el chat: no envía el mensaje por sí solo. Para un
envío automático hace falta el modo `CLOUD_API` o un proveedor equivalente.

Para probar correo, cambia el canal preferido a **Correo electrónico** en
**Mis datos**, confirma el email y vuelve a despachar. En modo simulado el
contenido aparece en la consola y el mensaje queda como `SIMULADO`; no se envía
nada a Internet.

## Configurar Cloud API

En PowerShell, antes de iniciar el servidor:

```powershell
$env:WHATSAPP_MODE = "CLOUD_API"
$env:WHATSAPP_CLOUD_API_TOKEN = "token-de-meta"
$env:WHATSAPP_PHONE_NUMBER_ID = "identificador-del-numero"
$env:WHATSAPP_API_VERSION = "v23.0"
```

Variables disponibles:

| Variable | Uso |
|---|---|
| `WHATSAPP_MODE` | `SIMULADO` o `CLOUD_API` |
| `WHATSAPP_CLOUD_API_TOKEN` | Token de acceso de la app de Meta |
| `WHATSAPP_PHONE_NUMBER_ID` | Identificador del número emisor en Meta |
| `WHATSAPP_API_VERSION` | Versión de Graph API; por defecto `v23.0` |
| `WHATSAPP_TIMEOUT_SECONDS` | Tiempo máximo de espera HTTP; por defecto 10 |

El adaptador envía mensajes de tipo texto a
`https://graph.facebook.com/{version}/{phone_number_id}/messages`. Para mensajes
iniciados por el negocio, Meta puede exigir una plantilla aprobada y opt-in del
destinatario. La demo no administra plantillas ni conversaciones entrantes:
revisa la documentación vigente de Meta antes de usar un número real.

Fuera de una ventana de servicio de 24 horas, Meta normalmente solo permite
plantillas aprobadas. Para una prueba rápida se puede hacer que el paciente
envíe primero un mensaje al número de la clínica; eso abre la ventana, pero no
reemplaza las plantillas para recordatorios automáticos programados con días de
anticipación. El adaptador actual no envía `type: template`; si se usa un número
real para recordatorios, hay que crear las plantillas en Meta y ampliar el
adaptador con sus nombres, idioma y parámetros.

Si faltan credenciales o el destinatario no tiene un número válido, el mensaje
queda pendiente y se reintenta al volver a despachar. Después de tres intentos
pasa a `FALLIDO` y se crea una alerta operativa.

## Correo electrónico

El correo usa el mismo outbox y los mismos eventos. Solo se encola si el
paciente tiene canal preferido `EMAIL`, un correo registrado y consentimiento;
el portal recibe siempre una copia.

| Modo | Qué hace | Credenciales |
|---|---|---|
| `SIMULADO` (por defecto) | Imprime el correo en la consola y deja el estado `SIMULADO`. | No requiere |
| `SMTP` | Envía con el backend SMTP de Django y deja el estado `ENVIADO`. | Host, puerto, usuario y contraseña |

La forma recomendada es copiar `.env.example` a `.env` en la raíz del proyecto
y completar los valores. Django carga `.env` automáticamente al iniciar y el
archivo está ignorado por Git. Las variables del entorno del sistema tienen
prioridad sobre el archivo; después de editarlo, reinicia waitress.

Ejemplo con Gmail:

```env
EMAIL_MODE=SMTP
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=tu-correo@gmail.com
EMAIL_HOST_PASSWORD=app-password
EMAIL_USE_TLS=1
EMAIL_USE_SSL=0
DEFAULT_FROM_EMAIL=Agendamiento Demo <tu-correo@gmail.com>
```

También puedes definirlas en PowerShell antes de arrancar el servidor:

```powershell
$env:EMAIL_MODE = "SMTP"
$env:EMAIL_HOST = "smtp.gmail.com"
$env:EMAIL_PORT = "587"
$env:EMAIL_HOST_USER = "tu-correo@gmail.com"
$env:EMAIL_HOST_PASSWORD = "app-password"
$env:EMAIL_USE_TLS = "1"
$env:EMAIL_USE_SSL = "0"
$env:DEFAULT_FROM_EMAIL = "Agendamiento Demo <tu-correo@gmail.com>"
```

Para un servidor institucional, usa el host, puerto y credenciales que entregue
el proveedor. Si usas SSL en el puerto 465, configura `EMAIL_USE_SSL=1` y
`EMAIL_USE_TLS=0`; no actives ambos. Para Gmail puede ser necesario activar
verificación en dos pasos y crear una contraseña de aplicación; revisa la
configuración vigente de Google.

El comando `motor` ejecuta la asignación automática y, al final, despacha
WhatsApp y correo por la misma cola. El comando `despachar` sigue disponible
para procesar solo el outbox. El correo automático puede ser gratuito o de bajo
costo según el proveedor, pero los límites y las condiciones cambian: verifícalos
antes de usarlo con pacientes.
No subas `.env` a Git, no escribas la contraseña SMTP en el repositorio y no la
compartas en capturas ni en el chat.

## Costos

El token de acceso de la API no se cobra. Meta cobra por mensaje **entregado**
(no por mensaje enviado), según la categoría y el país del destinatario. Los
mensajes que el paciente envía a la clínica no se cobran.

Tarifa de Chile en CLP vigente desde el 1 de octubre de 2026, según la hoja de
tarifas de Meta:

| Categoría | CLP por mensaje entregado |
|---|---:|
| Utilidad (confirmaciones, recordatorios) | 17,6584 |
| Marketing | 78,4917 |
| Servicio (después de 1.000 gratis al mes) | 17,6584 |
| Autenticación | 17,6584 |

Los mensajes de servicio tienen 1.000 unidades gratis por número de negocio y
mes; el resto se cobra. Pueden aplicarse impuestos. Meta actualiza las tarifas
periódicamente: verifica la página oficial antes de presupuestar:
<https://developers.facebook.com/docs/whatsapp/pricing/>.

El "token" de un agente de IA de Meta es otro producto: se cobra por consumo de
tokens (USD 2 por millón, aproximadamente 4-5 centavos de dólar por mensaje).
La demo no usa ese agente.

## Motor automático

El comando siguiente ejecuta el ciclo completo: procesa eventos pendientes,
vence ofertas, asigna cupos a las solicitudes en espera, crea recordatorios y
despacha las notificaciones:

```powershell
.\.venv\Scripts\python.exe manage.py motor
```

Para ejecutar el motor sin enviar mensajes externos:

```powershell
.\.venv\Scripts\python.exe manage.py motor --sin-despacho
```

Para procesar solo el outbox, sin asignar cupos ni crear recordatorios:

```powershell
.\.venv\Scripts\python.exe manage.py despachar
```

El script `scripts\despachar_whatsapp.bat` ejecuta `motor` y guarda la salida en
`.deploy\despachar.log`. `scripts\despachar_whatsapp.vbs` lo ejecuta sin abrir
una consola, para programarlo con el Programador de tareas de Windows.

La tarea de la demo se llama **Agendamiento - Despachar notificaciones** y se
ejecuta cada minuto. Comprobar o desactivar:

```powershell
schtasks /Query /TN "Agendamiento - Despachar notificaciones" /V /FO LIST
schtasks /Change /TN "Agendamiento - Despachar notificaciones" /DISABLE
```

La tarea se ejecuta solo mientras el PC esté encendido y con las variables de
entorno del usuario que la creó. Para producción usa un servidor 24/7 o un
worker equivalente. Si `WHATSAPP_MODE` o `EMAIL_MODE` están en `SIMULADO`, la
tarea procesa la cola pero no contacta a Meta ni a un servidor SMTP; al cambiar
a `CLOUD_API` o `SMTP`, los nuevos mensajes usan el canal real correspondiente.

## Recordatorios

`motor` ya crea los recordatorios de 24 h en cada pasada. El comando siguiente
permite crearlos y despachar el outbox de forma manual:

```powershell
.\.venv\Scripts\python.exe manage.py recordatorios
```

Para revisar sin enviar:

```powershell
.\.venv\Scripts\python.exe manage.py recordatorios --sin-despacho
```

En producción se puede ejecutar `motor` cada minuto o separar la creación de
recordatorios cada hora del despacho cada minuto, con el Programador de tareas
de Windows, cron o un worker. La demo usa la tarea externa; la aplicación no
incluye un worker interno.

## Verificación

La suite completa incluye 59 pruebas. Las pruebas de canales cubren:

- generación de enlace `wa.me` y normalización de teléfono;
- oferta y confirmación en modo simulado;
- envío Cloud API con respuesta simulada y guardado del identificador;
- falta de credenciales, reintentos y alerta por fallo;
- rechazo, cancelación y recordatorio idempotente de 24 h;
- correo simulado y correo SMTP con backend de prueba;
- alcance de la bandeja por establecimiento, incluidas citas y ofertas del
  establecimiento.

## Límites y responsabilidad

- Los datos de la semilla son ficticios. No uses datos reales de pacientes.
- El token de Meta y la contraseña SMTP son secretos: no los escribas en el
  repositorio, en capturas ni en plantillas. Usa variables de entorno.
- El modo simulado es el recomendado para la presentación académica si no hay
  credenciales de Meta o SMTP.
- El correo no tiene cifrado de extremo a extremo. Para pacientes reales, evita
  incluir detalles clínicos sensibles y revisa consentimiento, privacidad y
  retención con quien corresponda.
- El adaptador no implementa webhooks, confirmaciones de entrega, lectura,
  respuestas entrantes, gestión de plantillas ni campañas masivas.
- La demo no certifica cumplimiento legal, clínico ni de protección de datos.
- SQLite y el despacho periódico no demuestran concurrencia ni entrega
  garantizada.
