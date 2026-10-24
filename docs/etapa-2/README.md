# Etapa 2 — Implementación de demostración

**Proyecto:** Sistema web de agendamiento médico de segundo nivel.
**Estado:** demo funcional, verificada localmente. No es un sistema de producción.
**Fecha:** 23 de octubre de 2026.

## 1. Resultado

Se implementó un monolito Django con:

- autenticación por sesión y perfiles de rol;
- gestión de pacientes, solicitudes, listas de espera, agendas, bloques y horas;
- ofertas temporales con aceptación, rechazo, vencimiento y liberación;
- citas confirmadas, cancelación, atención e inasistencia;
- propuestas de reagendamiento con aprobación o rechazo humano;
- portal del paciente con ofertas, horas, perfil, preferencias y notificaciones;
- alertas operativas, auditoría append-only y reportes con exportación CSV;
- notificaciones por outbox con entrega externa **simulada**;
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
| Notificaciones | Outbox en base + adaptador simulado |
| Pruebas | `manage.py test`, Django `TestCase` |

No se usaron Docker, PostgreSQL, Git, HTMX ni Tailwind. Esas decisiones de la Etapa 1 se conservan como recomendación, no como estado actual.

## 3. Módulos

- `core`: parámetros, alertas, auditoría, notificaciones, panel, reportes, salud.
- `accounts`: perfil, roles, permisos y decoradores.
- `gestion`: modelo de negocio, servicios, vistas y formularios.
- `portal`: vistas del paciente y aislamiento por propietario.

## 4. Reglas implementadas

- Una oferta no es una cita; al aceptar se revalida la hora.
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
- Suite `gestion`: **26 pruebas aprobadas**.
- Smoke test de vistas internas con `admin`, `some`, `admision` y `medico`.
- Smoke test del portal con el paciente de demo.
- Smoke test de administración Django.
- Prueba de flujo integral: aprobación y rechazo de propuestas, suspensión de agenda, aceptación y cancelación de cita, perfil, preferencias, notificaciones, alta de paciente, solicitud, agenda, generación, publicación, suspensión, reportes, CSV y permisos clínicos.

## 7. Limitaciones principales

1. SQLite no permite demostrar concurrencia multiproceso real; el bloqueo es de proceso.
2. No hay entrega externa real de notificaciones.
3. No hay worker ni scheduler; el motor se ejecuta manualmente.
4. No hay integración clínica, HL7/FHIR, facturación ni ficha institucional.
5. No hay activación de cuentas, recuperación de contraseña ni segundo factor.
6. No hay pantalla dedicada para oferta o reserva manual; el flujo principal es automático.
7. No hay doble aprobación de reagendamientos.
8. No se validó cumplimiento legal ni seguridad institucional.
9. No hay repositorio Git en el entorno.

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
