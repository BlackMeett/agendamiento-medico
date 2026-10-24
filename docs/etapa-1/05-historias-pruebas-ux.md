# 05 — Historias de usuario, criterios de aceptación, pruebas y UX

## 1. Historias de usuario prioritarias

| ID | Historia | Criterio de aceptación resumido |
|---|---|---|
| HU-01 | Como funcionario de admisión quiero registrar una solicitud para que el paciente entre al proceso. | Se crea con UUID, estado `INGRESADA` o `PENDIENTE_REVISION`, paciente, especialidad, origen y fecha; queda auditada; no se crea si falta un dato obligatorio. |
| HU-02 | Como funcionario quiero validar una solicitud para incorporarla a la lista de espera. | Solo desde `INGRESADA` o `PENDIENTE_REVISION`; registra `fecha_lista_espera`, pasa a `EN_LISTA_ESPERA` y deja historial. Una transición inválida se rechaza. |
| HU-03 | Como funcionario quiero ver la lista de espera filtrada y ordenada por antigüedad. | Filtros por especialidad, establecimiento, fecha, estado, disponibilidad y oferta; orden estable por fecha de ingreso, creación e ID; no muestra datos clínicos. |
| HU-04 | Como funcionario quiero crear una agenda y generar horas. | Valida profesional, especialidad, fechas, duración y superposición; genera horas sin duplicados; una agenda en borrador no se ofrece. |
| HU-05 | Como funcionario quiero bloquear o suspender una agenda para resolver una ausencia. | Las horas afectadas se cancelan; las citas afectadas generan propuestas; no se reagenda automáticamente sin aprobación. |
| HU-06 | Como sistema quiero ofrecer una hora liberada al paciente compatible más antiguo. | La hora está disponible; el candidato está activo, es compatible y no tiene oferta/cita; se crea una sola oferta `PENDIENTE`; se encola una notificación simulada. |
| HU-07 | Como paciente quiero aceptar una oferta para confirmar mi hora. | Solo mi oferta, vigente y pendiente; se revalida la hora; se crea una sola cita `CONFIRMADA`; la hora queda `OCUPADA`; se audita. |
| HU-08 | Como paciente quiero rechazar una oferta para que se evalúe a otro paciente. | La oferta pasa a `RECHAZADA`; la hora se libera; se evalúa al siguiente candidato; no se me vuelve a ofrecer la misma hora. |
| HU-09 | Como sistema quiero vencer ofertas sin respuesta para liberar la hora. | Al cumplirse el plazo, la oferta pasa a `VENCIDA`, la hora se libera y se evalúa al siguiente candidato; repetir el proceso no duplica acciones. |
| HU-10 | Como funcionario autorizado quiero revisar propuestas de reagendamiento. | Ve alternativas, aprueba una o rechaza; al aprobar se revalida la hora; sin permiso recibe 403; se notifica y audita. |
| HU-11 | Como paciente quiero consultar mis solicitudes, ofertas y horas sin ver datos de otros. | Solo ve sus datos; modificar un UUID en la URL devuelve 404/403; puede actualizar contactos y disponibilidad. |
| HU-12 | Como funcionario quiero ver indicadores y alertas para gestionar la red. | Panel con filtros de establecimiento, especialidad y período; cifras calculadas desde datos; alertas de falta de candidatos, propuestas pendientes y fallos de notificación. |
| HU-13 | Como auditor quiero revisar quién cambió qué y cuándo. | Cada acción relevante deja actor, acción, entidad, estado anterior/nuevo, motivo, resultado y correlación; la auditoría no se edita desde la aplicación. |
| HU-14 | Como administrador quiero configurar plazos y parámetros sin cambiar código. | Los cambios se validan, se auditan y afectan nuevas operaciones; no alteran retroactivamente ofertas ya emitidas. |
| HU-15 | Como equipo quiero ejecutar pruebas de concurrencia para confiar en las reservas. | Dos procesos que compiten por la misma hora producen una sola cita; el perdedor recibe un conflicto controlado; no hay ofertas duplicadas. |

## 2. Criterios de aceptación transversales

- Toda acción destructiva o irreversible exige confirmación y motivo.
- Todo error de validación se muestra junto al campo y en un resumen accesible.
- Toda operación crítica tiene pruebas unitarias y de integración.
- Toda vista interna exige autenticación y permiso.
- Toda vista de paciente filtra por propietario.
- Toda operación automática tiene clave idempotente y correlación.
- Toda notificación externa es simulada y visible como tal.
- Ningún listado administrativo incluye datos clínicos.
- Ninguna hora se confirma sin revalidación.
- Ninguna propuesta de ausencia médica se confirma sin aprobación humana.

## 3. Plan de pruebas

### 3.1 Niveles

| Nivel | Herramienta | Qué cubre |
|---|---|---|
| Unitario | `pytest` | Reglas de compatibilidad, orden, estados, vencimiento, permisos. |
| Integración | `pytest-django` + PostgreSQL | Servicios, transacciones, restricciones, vistas y formularios. |
| Concurrencia | `TransactionTestCase` + hilos/conexiones | Doble reserva, doble oferta, reintentos. |
| Seguridad | Cliente de pruebas | IDOR, CSRF, autorización, sesión. |
| Extremo a extremo | Playwright (opcional) | Flujo funcionario y flujo paciente en navegador. |
| Manual guiada | Guion de demostración | Instalación limpia, datos de demo, operación completa. |

### 3.2 Pruebas obligatorias de reagendamiento

| # | Escenario | Resultado esperado |
|---|---|---|
| 1 | Hora liberada con varios candidatos | Se ofrece al compatible más antiguo. |
| 2 | El paciente acepta | Se crea una cita `CONFIRMADA`; la hora queda `OCUPADA`; la oferta `ACEPTADA`. |
| 3 | El paciente rechaza | Oferta `RECHAZADA`; hora liberada; se evalúa al siguiente candidato. |
| 4 | El paciente no responde | Al vencer el plazo, oferta `VENCIDA`; hora liberada; siguiente candidato. |
| 5 | No hay candidatos compatibles | No se crea oferta; se genera alerta operativa; la solicitud sigue activa. |
| 6 | Se cancela una agenda completa | Se identifican citas afectadas; se generan propuestas; no se confirma nada sin aprobación. |
| 7 | Dos procesos compiten por la misma hora | Solo uno crea la cita; el otro recibe conflicto; no hay doble reserva. |
| 8 | Solicitud cerrada | No recibe oferta. |
| 9 | Hora bloqueada o agenda suspendida | No puede asignarse. |
| 10 | Oferta duplicada | No produce dos reservas; la restricción o la idempotencia lo impide. |
| 11 | Paciente intenta ver datos de otro | 403/404; no se filtra información. |
| 12 | Usuario sin permiso intenta aprobar | 403; no se modifica la propuesta. |
| 13 | Falla la notificación | La reserva permanece; el mensaje queda `FALLIDO`; el reintento no duplica la reserva ni el mensaje. |
| 14 | Reintento de una operación completada | No se repite la oferta, cita ni notificación. |
| 15 | Cambio relevante | Queda en auditoría con actor, antes/después, motivo y correlación. |

### 3.3 Casos límite adicionales

- Dos solicitudes con la misma fecha de ingreso: desempate determinista.
- Paciente con dos solicitudes activas: no recibe dos ofertas simultáneas.
- Paciente con una cita superpuesta: no se le ofrece otra hora incompatible.
- Oferta aceptada justo después del vencimiento: se rechaza y se libera.
- Oferta aceptada mientras se suspende la agenda: gana una transacción; la otra se resuelve con conflicto.
- Propuesta aprobada cuando la hora ya fue tomada: pasa a `FALLIDA`; no se fuerza.
- Agenda con hora duplicada: la generación es idempotente.
- Cambio de horario de verano/invierno: las horas se muestran correctamente en `America/Santiago`.
- Mensaje con datos clínicos: la plantilla no los incluye; prueba de contenido.
- CSV con fórmula maliciosa: se neutraliza.
- Paciente sin correo ni teléfono: se usa canal portal y se alerta; no se inventa contacto.
- Reintento tras caída del trabajador: el evento sigue pendiente y se procesa una vez.
- Auditoría intenta actualizarse: la base lo impide.
- Usuario desactivado con sesión abierta: se rechaza la siguiente operación.

### 3.4 Datos de prueba

- Semilla reproducible con pacientes ficticios, profesionales ficticios, agendas demo y solicitudes con fechas relativas.
- Nombres como “Paciente Demo 001”; documentos sintéticos válidos; correos en dominio de ejemplo.
- Un parámetro `modo_demo` y un banner visible.
- Reloj congelado en pruebas para vencimientos y reportes.
- Factories para crear entidades sin depender de la semilla.

### 3.5 Cómo se ejecutarán

```powershell
# Desde la raíz del proyecto, en Windows
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_demo
.\.venv\Scripts\python.exe manage.py test gestion -v 2
.\.venv\Scripts\python.exe manage.py runserver
```

Resultado esperado: base SQLite demo creada, migraciones aplicadas, datos ficticios cargados y suite en verde. La demo no ejecuta pruebas de concurrencia multiproceso; para eso se requiere PostgreSQL y un entorno adicional.

## 4. Diseño visual y experiencia de usuario

### 4.1 Principios

- Claridad operativa: la tarea principal de cada pantalla se identifica en menos de 5 segundos.
- Densidad controlada: tablas cómodas, filtros visibles y acciones agrupadas.
- Estado siempre visible: chips con texto y color, no solo color.
- Prevención de errores: confirmaciones, validaciones y mensajes explicativos.
- Consistencia: mismos componentes, espaciado y patrones en todo el sistema.
- Accesibilidad: HTML semántico, foco visible, contraste, etiquetas y navegación por teclado.
- Responsive: tablas que se convierten en tarjetas en móvil; portal simplificado.
- Privacidad visual: datos enmascarados por defecto; sin información clínica en listados.

### 4.2 Identidad visual

| Elemento | Propuesta |
|---|---|
| Color primario | Azul petróleo `#0F6B78` |
| Color secundario | Verde salud `#2E7D5B` |
| Fondo | Gris muy claro `#F6F8FA` |
| Superficie | Blanco `#FFFFFF` |
| Texto | Gris azulado `#1F2933` |
| Advertencia | Ámbar `#B7791F` |
| Error | Rojo `#B42318` |
| Éxito | Verde `#067647` |
| Tipografía | Inter o similar, con fallback del sistema |
| Radios | 8–12 px |
| Espaciado | Escala de 4, 8, 12, 16, 24, 32 px |

Los colores exactos se validarán con una prueba de contraste WCAG AA.

### 4.3 Estructura interna

- Barra lateral con secciones: Panel, Pacientes, Solicitudes, Lista de espera, Agendas, Ofertas, Reagendamientos, Reportes, Auditoría, Configuración.
- Barra superior con establecimiento activo, rol, usuario y cierre de sesión.
- Migas de pan en pantallas profundas.
- Contenido principal con título, acciones primarias y filtros.
- Panel de alertas y actividad reciente.
- Banner persistente de “Entorno de demostración — datos ficticios”.

### 4.4 Portal del paciente

- Navegación simple: Inicio, Mis solicitudes, Mis horas, Ofertas, Mis datos.
- Tarjetas grandes y legibles.
- Acciones de aceptar/rechazar con confirmación y explicación del plazo.
- Sin menús administrativos ni información de otros pacientes.
- Instrucciones administrativas autorizadas.
- Formulario de contacto y disponibilidad con validación accesible.

### 4.5 Pantallas mínimas

| Pantalla | Contenido | Etapa |
|---|---|---|
| Login interno | Email, contraseña, recuperación, errores. | 3 |
| Panel | Indicadores, alertas, actividad. | 8 |
| Pacientes | Listado, búsqueda, ficha, contactos, historial. | 4 |
| Solicitudes | Listado, filtros, ficha, estados, historial. | 4 |
| Lista de espera | Tabla filtrable, posición, espera, oferta pendiente. | 4 |
| Agendas | Calendario/lista, creación, bloques, horas. | 5 |
| Ofertas | Pendientes, respondidas, vencidas, detalle. | 6 |
| Reagendamientos | Propuestas, alternativas, aprobar/rechazar. | 6 |
| Reportes | Indicadores, fórmulas, filtros, CSV. | 8 |
| Auditoría | Búsqueda por entidad, actor, fecha y correlación. | 3 |
| Portal | Inicio, solicitudes, ofertas, horas, datos. | 7 |

### 4.6 Estados de interfaz

Cada pantalla debe prever:

- Cargando.
- Vacío con explicación y acción sugerida.
- Error recuperable.
- Sin permiso.
- Éxito con confirmación.
- Conflicto de concurrencia con mensaje claro.

### 4.7 Accesibilidad

- Objetivo: WCAG 2.1 AA en las pantallas principales, sin afirmar certificación.
- Formularios con `label`, ayuda y errores asociados.
- Foco visible y orden lógico.
- Contraste mínimo 4.5:1 para texto normal.
- No usar solo color para comunicar estado.
- Tablas con encabezados y resumen.
- Diálogos con trampa de foco y cierre por teclado.
- Mensajes de error anunciados a lectores de pantalla.
- Idioma declarado `es-CL`.
- Pruebas manuales con teclado y zoom al 200%.

### 4.8 Microcopy

Ejemplos:

- “La hora sigue disponible. Revisa los datos antes de confirmar.”
- “Esta oferta venció. La hora será ofrecida a la siguiente persona en la lista.”
- “No tienes permiso para aprobar propuestas de reagendamiento.”
- “El mensaje fue registrado en modo simulación. No se envió a un proveedor externo.”
- “La hora ya fue tomada por otro proceso. Actualiza la página para ver la disponibilidad actual.”
