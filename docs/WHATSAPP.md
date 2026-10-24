# WhatsApp en la demo

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
y tiene teléfono/consentimiento, también se encola el mensaje externo:

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

Si faltan credenciales o el destinatario no tiene un número válido, el mensaje
queda pendiente y se reintenta al volver a despachar. Después de tres intentos
pasa a `FALLIDO` y se crea una alerta operativa.

## Recordatorios

El comando siguiente crea recordatorios para citas confirmadas que comienzan
dentro de las próximas 24 horas y luego despacha el outbox:

```powershell
.\.venv\Scripts\python.exe manage.py recordatorios
```

Para revisar sin enviar:

```powershell
.\.venv\Scripts\python.exe manage.py recordatorios --sin-despacho
```

En producción se debe programar cada hora con el Programador de tareas de
Windows, cron o un worker. La demo no trae un planificador activo.

## Verificación

La suite completa incluye 54 pruebas. Las pruebas de WhatsApp cubren:

- generación de enlace `wa.me` y normalización de teléfono;
- oferta y confirmación en modo simulado;
- envío Cloud API con respuesta simulada y guardado del identificador;
- falta de credenciales, reintentos y alerta por fallo;
- rechazo, cancelación y recordatorio idempotente de 24 h;
- alcance de la bandeja por establecimiento, incluidas citas y ofertas del
  establecimiento.

## Límites y responsabilidad

- Los datos de la semilla son ficticios. No uses datos reales de pacientes.
- El token es un secreto: no lo escribas en el repositorio, en capturas ni en
  plantillas. Usa variables de entorno.
- El modo simulado es el recomendado para la presentación académica si no hay
  credenciales de Meta.
- El adaptador no implementa webhooks, confirmaciones de entrega, lectura,
  respuestas entrantes, gestión de plantillas ni campañas masivas.
- La demo no certifica cumplimiento legal, clínico ni de protección de datos.
- SQLite y el despacho manual no demuestran concurrencia ni entrega garantizada.
