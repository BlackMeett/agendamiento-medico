# Etapa 2 — Implementación de demostración

**Proyecto:** Sistema web de agendamiento médico de segundo nivel.
**Estado:** demo funcional, verificada localmente. No es un sistema de producción.
**Fecha:** 24 de octubre de 2026.

## 1. Resultado

Se implementó un monolito Django con:

- autenticación por sesión y perfiles de rol;
- gestión de pacientes, solicitudes, listas de espera, agendas, bloques y horas;
- ofertas temporales con aceptación, rechazo, vencimiento y liberación;
- citas confirmadas, cancelación, atención e inasistencia;
- propuestas de reagendamiento con aprobación o rechazo humano;
- portal del paciente con solicitud de hora por especialidad, asignación automática o elección manual de una hora, ofertas, horas, perfil, preferencias y notificaciones;
- alertas operativas, auditoría append-only y reportes con exportación CSV;
- notificaciones por outbox con WhatsApp simulado y adaptador opcional para WhatsApp Business Cloud API;
- datos ficticios reproducibles mediante `seed_demo`;
- pruebas automatizadas de dominio y seguridad.

## 2. Stack real

| Componente | Implementación |
|---|---|
| Lenguaje | Python 3.12 |
| Framework | Django 5.2.18 |
| Base de datos | SQLite local |
| Interfaz | Plantillas Django + CSS propio |
| Zona horaria | `America/Santiago`, locale `es-cl` |
| Notificaciones | Outbox en base + WhatsApp simulado o Cloud API opcional |
| Pruebas | `manage.py test`, Django `TestCase` |

No se usaron Docker, PostgreSQL, HTMX ni Tailwind. Esas decisiones de la Etapa 1 se conservan como recomendación, no como estado actual.

## 3. Módulos

- `core`: parámetros, alertas, auditoría, notificaciones, panel, reportes, salud.
- `accounts`: perfil, roles, permisos y decoradores.
- `gestion`: modelo de negocio, servicios, vistas y formularios.
- `portal`: vistas del paciente y aislamiento por propietario.

## 4. Reglas implementadas

- Una oferta no es una cita; al aceptar se revalida la hora.
- El paciente puede crear una solicitud por especialidad desde el portal con dos modos: asignación automática o elección de una hora disponible.
- En el modo automático, la solicitud se incorpora a la lista de espera y el sistema intenta ofrecer la primera hora compatible; si no existe, queda esperando.
- En el modo manual, el paciente elige una hora de la especialidad y el servicio revalida disponibilidad, especialidad, citas activas y superposiciones antes de crear la cita confirmada. No se crea una oferta temporal.
- La solicitud desde portal no asigna prioridad clínica: el orden es por fecha de ingreso.
- Una solicitud no puede tener dos ofertas pendientes ni dos citas activas.
- Las horas se bloquean con transacciones y restricciones únicas.
- El vencimiento libera la hora y devuelve la solicitud a la lista.
- El rechazo de una oferta genera un evento para el siguiente candidato.
- Suspender una agenda cancela ofertas pendientes y crea propuestas para citas futuras confirmadas.
- Aprobar una propuesta verifica nuevamente que la hora siga disponible.
- Si la propuesta ya no es viable, queda en estado `FALLIDA` y se crea una alerta; esto persiste aunque la vista muestre el error.
- Un evento fallido del motor queda en estado `FALLIDO` con su alerta, en lugar de desaparecer por el rollback.
- La inasistencia no aplica sanciones automáticas.
- No se introducen prioridades clínicas ni plazos institucionales inventados.

## 5. Seguridad aplicada

- Autorización en servidor por rol y por establecimiento.
- Paciente vinculado a un usuario; el portal solo muestra sus datos.
- Filtros de queryset para pacientes, solicitudes, agendas, ofertas y citas.
- Formularios de pacientes, solicitudes y agendas limitados al establecimiento del usuario.
- Acciones mutables por `POST` y CSRF de Django.
- Auditoría de acciones relevantes; no se edita ni elimina desde la aplicación.
- Exportación CSV con escape de fórmulas.
- Contraseñas con el hasher de Django.

## 6. Verificación realizada

- `manage.py check`: sin errores.
- Suite completa: **54 pruebas aprobadas** (dominio, permisos, portal, reserva manual y WhatsApp).
- Smoke test de vistas internas con `admin`, `some`, `admision` y `medico`.
- Smoke test del portal con el paciente de demo.
- Smoke test de administración Django.
- Prueba de flujo integral: aprobación y rechazo de propuestas, suspensión de agenda, aceptación y cancelación de cita, perfil, preferencias, notificaciones, alta de paciente, solicitud, agenda, generación, publicación, suspensión, reportes, CSV y permisos clínicos.

## 7. Limitaciones principales

1. SQLite no permite demostrar concurrencia multiproceso real; el bloqueo es de proceso.
2. Por defecto no hay entrega externa real de notificaciones. WhatsApp puede usar Cloud API si se configuran credenciales, pero no se incluyen ni se validaron con una cuenta real.
3. No hay worker ni scheduler; el motor y los recordatorios se ejecutan manualmente o con una tarea externa.
4. No hay integración clínica, HL7/FHIR, facturación ni ficha institucional.
5. No hay activación de cuentas, recuperación de contraseña ni segundo factor.
6. No hay pantalla de funcionario para crear una oferta manual; el paciente puede elegir una hora desde el portal y el flujo automático sigue siendo el principal para la lista de espera.
7. No hay doble aprobación de reagendamientos.
8. No se validó cumplimiento legal ni seguridad institucional.

## 8. Reproducción

Consultar el `README.md` de la raíz. Comandos mínimos:

```powershell
cd C:\Users\Usuario\proyectos\agendamiento-medico
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_demo
.\.venv\Scripts\python.exe manage.py runserver
```

Para pruebas:

```powershell
.\.venv\Scripts\python.exe manage.py test gestion -v 2
```

## 9. Siguientes pasos recomendados

1. Migrar a PostgreSQL y ejecutar pruebas de concurrencia con múltiples procesos.
2. Implementar un worker/scheduler para eventos, vencimientos y notificaciones.
3. Reemplazar el adaptador simulado por un proveedor real con consentimiento y rebotes.
4. Agregar activación de cuentas, recuperación de acceso y segundo factor.
5. Definir con la institución reglas de prioridad, plazos, agendas, feriados y doble control.
6. Revisar legalidad, privacidad, retención, respaldo y respuesta a incidentes.
7. Preparar despliegue con HTTPS, observabilidad, límites de tasa y soporte.
