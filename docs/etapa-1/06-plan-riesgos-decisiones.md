# 06 — Plan, riesgos y decisiones pendientes

## 1. Plan de implementación por etapas

Cada etapa termina con una demostración verificable, pruebas y documentación. No se avanza si la anterior no cumple sus criterios.

### Etapa 2 — Preparación del entorno

Entregables:

- Repositorio y estructura de carpetas.
- `docker-compose.yml` con PostgreSQL.
- Proyecto Django y configuración por entornos.
- `.env.example`, `.gitignore`, `requirements`.
- Tailwind y HTMX configurados.
- Modelo de usuario personalizado y migración inicial.
- Comando `seed_demo` con datos ficticios.
- Pantalla base, health check y manejo de errores.
- README con instalación, migraciones, ejecución y pruebas.

Criterios de aceptación:

- `docker compose up -d db` levanta PostgreSQL.
- `python manage.py migrate` termina sin errores.
- `python manage.py seed_demo` carga datos identificados como demo.
- `python manage.py runserver` muestra la pantalla base.
- `pytest` ejecuta al menos una prueba de humo y termina en verde.
- Un integrante distinto puede repetir los pasos desde cero.

### Etapa 3 — Autenticación, permisos y estructura base

Entregables:

- Login, logout y recuperación de acceso.
- Roles, permisos y alcance por establecimiento.
- Activación de cuentas de paciente.
- Layout interno y portal base.
- Auditoría inicial y correlación.
- Páginas 403, 404 y 500.
- Pruebas de autenticación y autorización.

Criterios de aceptación:

- Un usuario sin permiso recibe 403 en la vista y en el servicio.
- Un paciente no puede acceder a URLs internas.
- El login fallido se registra sin guardar contraseña.
- El cierre de sesión es por POST.
- La auditoría registra login, logout y cambios de rol.
- Las pruebas de permisos pasan.

### Etapa 4 — Pacientes, solicitudes y lista de espera

Entregables:

- CRUD administrativo de pacientes y contactos.
- Preferencias de disponibilidad.
- Registro y validación de solicitudes.
- Datos clínicos separados y restringidos.
- Máquina de estados e historial.
- Lista de espera con filtros y orden.
- Detección de duplicados y alertas.
- Pruebas de transiciones y permisos.

Criterios de aceptación:

- No se crea un paciente con documento duplicado.
- Una solicitud incompleta queda en revisión y explica qué falta.
- Una transición inválida se rechaza y no cambia el estado.
- La lista se ordena por antigüedad y desempate determinista.
- El personal administrativo no ve datos clínicos.
- Cada cambio deja historial y auditoría.

### Etapa 5 — Agendas y disponibilidad

Entregables:

- Establecimientos, especialidades, profesionales y tipos de prestación.
- Agendas, bloques y horas.
- Generación manual y configurable.
- Bloqueo, suspensión y cancelación.
- Validaciones de superposición y duplicados.
- Pruebas de integridad.

Criterios de aceptación:

- No se publican agendas superpuestas del mismo profesional.
- La generación repetida no duplica horas.
- Una hora bloqueada o de agenda suspendida no se ofrece.
- Suspender una agenda afecta las citas y genera propuestas.
- Cada cambio de agenda queda auditado.

### Etapa 6 — Motor de asignación y reagendamiento

Orden de trabajo:

1. Reglas puras y pruebas unitarias.
2. Eventos e idempotencia.
3. Ofertas y vencimientos.
4. Aceptación y confirmación.
5. Rechazo y siguiente candidato.
6. Propuestas por ausencia médica.
7. Pruebas de concurrencia y reintentos.

Entregables:

- Reglas de compatibilidad documentadas.
- Orden por antigüedad y desempate.
- Cola de eventos.
- Ofertas con ciclo de vida.
- Confirmación transaccional.
- Vencimiento y reintentos.
- Propuestas y aprobación humana.
- Alertas por falta de candidatos.
- Suite de las 15 pruebas obligatorias.

Criterios de aceptación:

- Una hora liberada se ofrece al candidato compatible más antiguo.
- Aceptar crea una sola cita y revalida la hora.
- Rechazar o vencer libera la hora y evalúa al siguiente.
- Dos procesos concurrentes no reservan la misma hora.
- Un reintento no duplica ofertas, citas ni mensajes.
- Una agenda suspendida no se reagenda sin aprobación.
- Todas las pruebas de la sección 10 del encargo están cubiertas.

### Etapa 7 — Portal y notificaciones

Entregables:

- Portal del paciente responsive.
- Consulta de solicitudes, ofertas, citas y cambios.
- Aceptar y rechazar ofertas.
- Actualización de contactos y disponibilidad.
- Outbox y adaptador simulado.
- Plantillas sin datos clínicos.
- Reintentos, deduplicación y alertas.
- Pruebas de aislamiento y notificación.

Criterios de aceptación:

- El paciente solo ve sus datos.
- Cambiar un UUID en la URL no expone otro paciente.
- Aceptar/rechazar solo funciona sobre ofertas propias y vigentes.
- El mensaje simulado queda registrado y visible como simulado.
- Un fallo de notificación no altera la reserva.
- Un reintento no duplica el mensaje.

### Etapa 8 — Panel y reportes

Entregables:

- Panel con indicadores, filtros y alertas.
- Reportes con fórmula, origen y limitaciones.
- Exportación CSV segura.
- Pruebas con datos conocidos.

Criterios de aceptación:

- Los cálculos coinciden con un conjunto de datos de prueba.
- Los filtros por establecimiento, especialidad y período funcionan.
- Se distingue dato real de dato demo.
- La exportación respeta permisos, escapa fórmulas y se audita.
- No se presentan metas institucionales inventadas.

### Etapa 9 — Pruebas integrales y documentación

Entregables:

- Pruebas de extremo a extremo.
- Guion de demostración.
- Manual de instalación, operación y recuperación.
- Limitaciones conocidas.
- Procedimiento de respaldo y restauración.
- Revisión de seguridad y dependencias.

Criterios de aceptación:

- Una instalación limpia completa el flujo de demostración.
- Las pruebas unitarias, de integración y concurrencia pasan.
- El flujo funcionario y el flujo paciente funcionan en navegador.
- La documentación permite repetir la demo sin ayuda del equipo.
- Los riesgos y pendientes están actualizados.

### Etapa 10 — Revisión final

Entregables:

- Matriz requisito → estado: implementado, parcial, pendiente o bloqueado.
- Evidencia de prueba por requisito.
- Lista de deuda técnica.
- Lista de decisiones que requieren validación externa.
- Guion de defensa universitaria.

Criterios de aceptación:

- Ninguna función se marca “implementada” solo por tener una pantalla.
- Cada función implementada tiene lógica, permisos, auditoría y prueba.
- Las funciones bloqueadas explican qué decisión externa falta.
- El sistema se presenta como demostración académica, no como producto clínico certificado.

## 2. Decisiones críticas pendientes

| # | Decisión | Valor de demo | Impacto | Quién debe validar | ¿Bloquea la Etapa 2? |
|---|---|---|---|---|---|
| 1 | Especialidad inicial | “Especialidad Demo” | Contenido y agenda | Referente clínico y académico | No |
| 2 | Campos de identificación y contacto | Documento sintético, nombre, fecha de nacimiento, teléfono, correo | Privacidad y duplicados | Jurídico y negocio | No |
| 3 | Reglas de compatibilidad | Especialidad, establecimiento, disponibilidad declarada, sin duplicados ni superposición | Asignación y equidad | Negocio y clínica | No para demo; sí para operación |
| 4 | Duración de consulta | 30 min | Capacidad | Referente clínico | No |
| 5 | Jornadas y cupos | 08:00–12:00 y 14:00–17:00 | Capacidad | Referente clínico | No |
| 6 | Plazo de respuesta de oferta | 48 h | Cupos y espera | Negocio | No |
| 7 | Reserva temporal | La oferta bloquea la hora | Disponibilidad | Negocio | No |
| 8 | Recordatorios | Desactivados en demo; plantilla preparada | Operación | Negocio | No |
| 9 | Consecuencias de rechazo, inasistencia y silencio | Sin sanción automática; vuelve a lista con alerta | Equidad y adherencia | Negocio y jurídico | No |
| 10 | Perfiles y autorizaciones definitivas | Matriz propuesta | Seguridad y segregación | Dirección y seguridad | No |
| 11 | Proveedores de SMS, correo y WhatsApp | Solo simulación | Notificaciones reales | Institución | No; bloquea envío real |
| 12 | Integraciones externas | Ninguna | Interoperabilidad | Institución | No |
| 13 | Normas institucionales y legales | Pendientes | Operación con datos reales | Jurídico y autoridad sanitaria | No; bloquea producción |
| 14 | Volumen esperado | Datos demo pequeños | Rendimiento y arquitectura | Institución | No |
| 15 | Configuración y despliegue definitivos | Local | Operación | Institución | No |

Ninguna de estas decisiones impide construir la demostración académica. Todas las que afectan reglas quedan como parámetros o como valores de semilla explícitamente marcados.

## 3. Riesgos y contradicciones

| Riesgo o tensión | Explicación | Mitigación |
|---|---|---|
| “Automático” vs aprobación humana | El encargo pide reagendamiento automático, pero también aprobación humana en ausencias médicas. | Dos rutas: oferta automática con aceptación del paciente; propuesta con aprobación humana para agendas suspendidas. |
| FIFO vs compatibilidad | El más antiguo puede no ser compatible con la hora. | FIFO solo entre candidatos compatibles. Se documenta que no es una prioridad clínica. |
| Paciente con disponibilidad estrecha | Puede quedar postergado mucho tiempo. | Alertas por intentos fallidos y revisión humana; no se ignora su restricción. |
| Oferta que bloquea la hora | Reduce la disponibilidad mientras se espera respuesta. | Vencimiento configurable, recordatorios y monitoreo de ofertas sin respuesta. |
| Propuesta que no bloquea la hora | Puede fallar al aprobar porque otro la tomó. | Revalidación obligatoria y estado `FALLIDA` con alerta; alternativa: reserva temporal con caducidad. |
| Reserva manual | Puede saltarse el orden de la lista. | Permiso explícito, motivo obligatorio, auditoría y alerta; no se presenta como priorización automática. |
| Datos clínicos | Riesgo de exposición en listados, logs o mensajes. | Tabla separada, permisos, minimización y pruebas de contenido. |
| Notificaciones simuladas | Puede creerse que el paciente fue contactado realmente. | Estado “SIMULADO”, banner y advertencia en la interfaz; no se afirma envío real. |
| Superusuario de Django | Puede saltarse permisos de la aplicación. | Cuenta reservada, auditoría, política de uso y revisión; no usar en la demo cotidiana. |
| Reportes malinterpretados | Un indicador descriptivo puede tomarse como meta o calidad clínica. | Fórmula, origen, exclusiones y limitaciones visibles; sin metas inventadas. |
| Zona horaria y horario de verano | Errores de una hora en agendas y reportes. | UTC en base, `America/Santiago` en presentación, pruebas de cambio de hora. |
| Solicitudes duplicadas | Dos solicitudes activas del mismo paciente y especialidad. | Advertencia, motivo, exclusión del motor y alerta; política definitiva pendiente. |
| Retención vs derecho de supresión | La historia y la auditoría deben conservarse. | Anonimización o restricción; procedimiento legal pendiente. |
| PostgreSQL obligatorio | Un equipo podría intentar SQLite y perder garantías. | Documentación explícita y pruebas que fallan si no hay PostgreSQL. |
| Complejidad para el equipo | Muchas reglas y estados. | Monolito modular, reglas puras, pruebas primero, entregas por etapa. |
| Sin prioridad clínica | El orden por antigüedad no refleja gravedad. | Se declara explícitamente; una prioridad clínica futura requiere reglas aprobadas y separadas. |

## 4. Matriz de trazabilidad inicial

| Requisito del encargo | Dónde se aborda | Estado de diseño |
|---|---|---|
| Autenticación y permisos | `04-seguridad-permisos.md` | Diseñado |
| Pacientes y duplicados | `03-modelo-datos.md` | Diseñado |
| Derivaciones y estados | `02-flujos-concurrencia.md` | Diseñado |
| Lista de espera | `02-flujos-concurrencia.md` | Diseñado |
| Agendas y bloques | `02-flujos-concurrencia.md`, `03-modelo-datos.md` | Diseñado |
| Motor y ofertas | `02-flujos-concurrencia.md` | Diseñado |
| Reagendamiento por ausencia | `02-flujos-concurrencia.md` | Diseñado |
| Portal | `02-flujos-concurrencia.md`, `05-historias-pruebas-ux.md` | Diseñado |
| Notificaciones | `02-flujos-concurrencia.md` | Diseñado |
| Panel y reportes | `05-historias-pruebas-ux.md` | Diseñado |
| Auditoría | `03-modelo-datos.md` | Diseñado |
| Pruebas obligatorias | `05-historias-pruebas-ux.md` | Planificado |
| Instalación local | `01-arquitectura.md` | Planificado |
| Seguridad y normativa | `04-seguridad-permisos.md` | Diseñado con validaciones pendientes |

## 5. Decisiones de la Etapa 1 y ajustes de la demo

1. **Stack:** Django 5.2 LTS. La implementación local usa SQLite y CSS propio; PostgreSQL, HTMX y Tailwind quedan como recomendación para producción.
2. **Arquitectura:** monolito modular, sin microservicios ni Redis/Celery en la primera versión.
3. **Modelo de oferta:** una oferta pendiente bloquea la hora; no se confirma sin aceptación; una oferta no es una cita.
4. **Reagendamiento por ausencia:** propuestas con aprobación humana; sin confirmación automática.
5. **Base de datos:** SQLite para la demo de un proceso; PostgreSQL es obligatorio para producción y para pruebas de concurrencia multiproceso.
6. **Ruta del proyecto:** `C:\Users\Usuario\proyectos\agendamiento-medico`.
7. **Alcance de la Etapa 2:** se implementaron entorno, estructura, migración inicial, semilla demo, pantallas, flujos y pruebas automatizadas.

## 6. Información útil para ajustar el diseño

Las preguntas originales se conservan como contexto histórico. El entorno utilizado fue Windows, Python 3.12 y Django; no había Docker, PostgreSQL ni Git disponibles.

- ¿El equipo ya programó en Python, JavaScript, PHP u otro lenguaje?
- ¿Alguien tiene experiencia con Django, Laravel o React?
- ¿El equipo usa Windows, macOS o Linux?
- ¿Está disponible Docker Desktop, o se prefiere PostgreSQL instalado nativamente?
- ¿La universidad exige alguna tecnología, base de datos o formato de entrega?
- ¿Se prefiere una especialidad ficticia neutra o una especialidad real solo como nombre de demostración?
- ¿Cuántas personas integran el equipo y cuánto tiempo tienen para el proyecto?

## 7. Estado de esta entrega

- Documentación de Etapa 1 creada en `C:\Users\Usuario\proyectos\agendamiento-medico\docs\etapa-1`.
- Implementación demo completada en `C:\Users\Usuario\proyectos\agendamiento-medico` con Django 5.2.18 y SQLite.
- Base de datos demo creada y cargada con `seed_demo`.
- Suite de 26 pruebas automatizadas aprobada.
- Flujos internos y portal verificados con datos ficticios.
- No se han cargado datos reales.
- La demo no es producción y no acredita cumplimiento legal ni clínico.
