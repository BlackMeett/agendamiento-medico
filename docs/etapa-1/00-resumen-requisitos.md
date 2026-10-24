# 00 — Resumen, requisitos y supuestos

## 1. El problema en una frase

Una red de salud de segundo nivel necesita ordenar el camino entre una derivación y una consulta especializada: recibir solicitudes, validarlas administrativamente, ponerlas en lista de espera, administrar agendas, ofrecer horas, obtener una respuesta del paciente, confirmar la reserva y resolver cancelaciones, inasistencias y ausencias médicas sin perder trazabilidad ni producir asignaciones dobles.

El sistema no diagnostica ni prioriza clínicamente. Su criterio inicial de orden es la **antigüedad de la solicitud entre candidatos administrativamente compatibles**.

## 2. Qué significa “automático” en este proyecto

“Reagendamiento automático” significa que el motor:

1. Detecta una hora liberada o una agenda afectada.
2. Identifica solicitudes compatibles.
3. Ordena por antigüedad.
4. Genera una **oferta** de hora.
5. Notifica al paciente.
6. Espera aceptación, rechazo o vencimiento.
7. Confirma la reserva solo si el paciente acepta y la hora sigue disponible.

No significa confirmar una hora sin aceptación del paciente. Tampoco significa reemplazar la aprobación humana cuando una regla institucional la exige, como ocurre en la suspensión de una jornada médica.

## 3. Límites del alcance académico

Incluido:

- Acceso interno para funcionarios y portal separado para pacientes.
- Roles, permisos y alcance por establecimiento.
- Fichas administrativas de pacientes, contactos y preferencias.
- Derivaciones y solicitudes con estados, historial y datos clínicos separados.
- Lista de espera consultable y filtrable.
- Establecimientos, especialidades, profesionales, agendas, bloques y horas.
- Motor de ofertas, aceptación, rechazo, vencimiento, cancelación y reagendamiento.
- Propuestas por ausencia médica con aprobación humana.
- Notificaciones simuladas y desacopladas.
- Panel administrativo, indicadores y exportación segura.
- Auditoría append-only y pruebas automatizadas.

Excluido de la primera versión:

- Integración con sistemas institucionales, fichas clínicas electrónicas o sistemas de interconsulta.
- Envío real de SMS, correo o WhatsApp.
- Diagnóstico, prescripción, telemedicina o decisiones clínicas.
- Priorización clínica automática.
- Facturación, convenios, copagos o gestión financiera.
- Aplicación móvil nativa.
- Despliegue institucional, certificación o operación con pacientes reales.
- Optimización avanzada de agendas, sobrecupo o algoritmos de investigación operativa.

## 4. Requisitos confirmados

### 4.1 Funcionales

| Área | Requisito confirmado |
|---|---|
| Usuarios | Autenticación de funcionarios y pacientes, cierre de sesión, recuperación de acceso y autorización en el servidor. |
| Roles | Perfiles diferenciados: administrador, SOME, admisión/derivación, profesional de salud, médico especialista y paciente. |
| Pacientes | Ficha administrativa, contactos, preferencias, establecimiento de referencia e historial de solicitudes y atenciones. |
| Duplicados | Prevención de pacientes duplicados y de solicitudes activas duplicadas, con revisión humana cuando corresponda. |
| Derivaciones | Orígenes APS, internas, externas, controles pendientes e ingreso manual autorizado. |
| Solicitudes | Identificador único, estados, fechas, historial de cambios y observaciones administrativas. |
| Datos clínicos | Separados de los datos administrativos y con acceso restringido. |
| Lista de espera | Filtros por especialidad, establecimiento, fecha, espera, estado, disponibilidad, ofertas e intentos. |
| Orden | Antigüedad de la solicitud compatible, con desempate determinista. |
| Agendas | Establecimientos, especialidades, profesionales, agendas, bloques, duración, cupos y fechas. |
| Disponibilidad | Creación manual y generación configurable de bloques y horas. |
| Restricciones | Sin superposición indebida, sin exceder cupos, sin asignar horas bloqueadas o canceladas. |
| Motor | Reaccionar a cancelaciones, liberaciones, inasistencias, cambios de agenda, rechazos y vencimientos. |
| Ofertas | Ciclo de vida explícito; una oferta pendiente no es una hora confirmada. |
| Confirmación | Revalidar disponibilidad al aceptar y confirmar dentro de una transacción. |
| Ausencia médica | Identificar afectados, proponer alternativas y exigir revisión humana. |
| Inasistencias | Consecuencias configurables; no se presume sanción ni cierre automático. |
| Portal | Consultar solicitudes, ofertas y horas; aceptar o rechazar; actualizar contactos y preferencias. |
| Notificaciones | Arquitectura desacoplada, adaptador simulado, estados, reintentos y deduplicación. |
| Panel | Resumen operativo, alertas, filtros y actividad reciente. |
| Reportes | Indicadores con fórmula, origen y limitaciones explícitas. |
| Auditoría | Registro de acciones manuales y automáticas, con actor, cambio, motivo y correlación. |
| Configuración | Parámetros modificables sin cambiar el código. |

### 4.2 No funcionales

- Modularidad y separación entre interfaz, servicios, dominio y persistencia.
- Reproducibilidad local con instrucciones exactas.
- Validación de entradas y mensajes de error comprensibles.
- Seguridad por defecto: contraseñas con hash, CSRF, XSS, inyección SQL, sesiones y autorización.
- Privacidad desde el diseño y minimización de datos.
- Trazabilidad de cambios y operaciones automáticas.
- Interfaz responsive y accesible en la medida técnicamente viable.
- Pruebas automatizadas de reglas críticas, permisos y concurrencia.
- Migraciones de base de datos versionadas.
- Configuración mediante variables de entorno.
- Documentación suficiente para que otro equipo pueda instalar, ejecutar y defender el proyecto.

## 5. Supuestos provisionales de demostración

Estos valores permiten construir y probar el sistema. **No son reglas oficiales de ningún Servicio de Salud.** Todos deben quedar en configuración y datos de demostración claramente identificados.

| ID | Supuesto | Valor inicial de demo | Dónde se configura | Riesgo si se usa sin validar |
|---|---|---|---|---|
| S1 | Especialidad inicial | “Especialidad Demo” | Semilla y parámetro | Bajo: es ficticia y reemplazable. |
| S2 | Duración de consulta | 30 minutos | Agenda y tipo de prestación | Alto si se usa para capacidad real. |
| S3 | Jornada de ejemplo | 08:00–12:00 y 14:00–17:00 | Generador de agendas | Alto si se usa para capacidad real. |
| S4 | Vigencia de una oferta | 48 horas | Parámetro del sistema | Alto: afecta cupos y tiempos de espera. |
| S5 | Reserva temporal | La oferta mantiene la hora bloqueada mientras está pendiente | Parámetro y diseño | Medio: reduce disponibilidad; evita doble asignación. |
| S6 | Reintentos de oferta por solicitud | 3 antes de generar alerta | Parámetro | Medio: es un umbral operativo, no una sanción. |
| S7 | Rechazo de oferta | Se cierra la oferta y se evalúa al siguiente candidato; la solicitud sigue activa | Regla configurable | Alto: debe validarse institucionalmente. |
| S8 | Falta de respuesta | La oferta vence y se evalúa al siguiente candidato; sin sanción automática | Regla configurable | Alto: debe validarse institucionalmente. |
| S9 | Inasistencia | La cita queda como inasistencia; la solicitud vuelve a lista con alerta; sin pérdida de prioridad | Regla configurable | Alto: debe validarse institucionalmente. |
| S10 | Desempate de antigüedad | Fecha de ingreso, luego fecha de creación, luego ID interno | Parámetro de orden | Bajo: es determinista y reproducible. |
| S11 | Fecha base de antigüedad | `fecha_ingreso` | Parámetro | Medio: una solicitud incompleta podría “saltar” al validarse. |
| S12 | Disponibilidad declarada | Restricción dura si el paciente la marca como tal | Preferencia del paciente | Medio: puede aumentar la espera de pacientes con disponibilidad estrecha. |
| S13 | Cuenta de paciente | Creación por funcionario con código de activación; sin autorregistro | Diseño de seguridad | Bajo: reduce suplantación. |
| S14 | Acceso a datos clínicos | Solo profesionales autorizados; el personal administrativo ve datos administrativos | Permisos | Crítico si se relaja. |
| S15 | Notificaciones | Solo adaptador simulado; se muestra “SIMULADO” en la interfaz | Configuración | Crítico si se confunde con envío real. |
| S16 | Zona horaria | Almacenar en UTC; mostrar `America/Santiago` | Configuración | Medio: afecta agendas y reportes. |
| S17 | Datos | 100% ficticios y con banner de demostración | Semilla y configuración | Crítico si se cargan datos reales. |
| S18 | Motor | Solo genera ofertas; nunca confirma sin aceptación | Diseño y pruebas | Crítico. |
| S19 | Reagendamiento por ausencia | Requiere aprobación humana | Regla configurable | Crítico. |
| S20 | PostgreSQL | Única base soportada para aceptación y concurrencia | Arquitectura | Alto: SQLite no permite demostrar concurrencia real. |

## 6. Decisiones que no se inventan

No se definirán sin validación:

- Especialidad real, campos definitivos de identificación, reglas clínicas, duraciones, jornadas, cupos, plazos, recordatorios, consecuencias de rechazo/inasistencia, perfiles definitivos, proveedores de mensajería, integraciones, normas institucionales, volúmenes y despliegue.

El detalle y el impacto de cada decisión está en `06-plan-riesgos-decisiones.md`.

## 7. Glosario mínimo

| Término | Significado en este proyecto |
|---|---|
| Solicitud | Caso administrativo que representa una necesidad de atención especializada. Puede originarse en una derivación. |
| Derivación | Documento o acto de origen que envía un paciente desde un establecimiento a otro. |
| Lista de espera | Vista consultable de solicitudes activas, no una tabla duplicada. |
| Hora médica | Cupo concreto de agenda, con profesional, fecha, inicio y fin. |
| Oferta | Propuesta de una hora a una solicitud, pendiente de respuesta. No es una reserva confirmada. |
| Cita | Reserva confirmada que ocupa una hora. |
| Reagendamiento | Cambio de una cita afectada por cancelación, ausencia médica u otra causa autorizada. |
| Propuesta | Alternativa de reagendamiento que requiere revisión humana. |
| Outbox | Cola transaccional de mensajes para enviar después del commit. |
| Idempotencia | Propiedad que permite repetir una operación sin duplicar su efecto. |
| FIFO | Primero en llegar, primero en ser atendido, aplicado solo entre candidatos compatibles. |
