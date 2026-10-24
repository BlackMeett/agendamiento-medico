# 04 — Seguridad, privacidad y permisos

## 1. Modelo de seguridad

La seguridad se aplica en el servidor. La interfaz puede ocultar opciones, pero nunca es la única defensa.

Capas:

1. Autenticación con sesión.
2. Autorización por permiso y por alcance.
3. Filtrado de datos por establecimiento y por paciente.
4. Validación de entrada y de transiciones de estado.
5. Restricciones de base de datos.
6. Auditoría de acciones y accesos relevantes.
7. Minimización de datos en pantallas, registros y notificaciones.

## 2. Autenticación

- Cuentas de funcionarios creadas por administración; sin autorregistro.
- Cuentas de pacientes creadas por funcionarios y activadas con código de un solo uso.
- Contraseñas con Argon2; nunca en texto plano ni en logs.
- Sesión con cookie `HttpOnly`, `Secure` en producción y `SameSite=Lax`.
- Rotación de sesión al iniciar sesión.
- Cierre de sesión por `POST`, no por enlace GET.
- Expiración por inactividad configurable; valor de demo: 30 minutos.
- Recuperación de acceso con token aleatorio, almacenado como hash, de un solo uso y con caducidad.
- Limitación de intentos con `django-axes` o equivalente; bloqueo temporal y auditoría.
- Mensajes de error genéricos en login para no revelar si un correo existe.
- Futuro: segundo factor para funciones administrativas y de aprobación.

## 3. Autorización

- Permisos con código, agrupados en roles.
- Alcance por establecimiento cuando corresponda.
- Alcance por relación: un médico ve las agendas y pacientes que le corresponden; un paciente ve solo sus datos.
- Verificación en cada vista, servicio y consulta.
- Filtros de queryset obligatorios; no se confía en el UUID de la URL.
- Pruebas de acceso directo a URLs de otro paciente, otro establecimiento y otra agenda.
- Separación de funciones: quien propone un reagendamiento no debería aprobarlo si la institución exige doble control. La matriz inicial es una propuesta; el rol supervisor queda pendiente.

## 4. Matriz inicial de permisos

Simbología:

- **✓:** permitido con alcance global o completo.
- **◐:** permitido solo dentro del establecimiento, agenda o cartera asignada.
- **P:** permitido solo sobre los propios datos del paciente.
- **—:** no permitido.
- **S:** ejecutado por el sistema, no por un usuario.

| Capacidad | Administrador | SOME | Admisión / derivación | Profesional de salud | Médico especialista | Paciente |
|---|---|---|---|---|---|---|
| Administrar usuarios y roles | ✓ | — | — | — | — | — |
| Configurar parámetros del sistema | ✓ | — | — | — | — | — |
| Ver auditoría | ✓ | — | — | — | — | — |
| Ver datos administrativos de pacientes | ◐ | ◐ | ◐ | ◐ | ◐ | P |
| Crear y editar pacientes | — | ◐ | ◐ | — | — | — |
| Ver documento completo del paciente | — | ◐ | ◐ | ◐ | ◐ | P |
| Ver datos clínicos de la solicitud | — | — | — | ◐ | ◐ | — |
| Registrar derivación o solicitud | — | ◐ | ◐ | ◐ | — | — |
| Validar administrativamente una solicitud | — | — | ◐ | — | — | — |
| Rechazar una solicitud | — | — | ◐ | — | — | — |
| Ver lista de espera | — | ◐ | ◐ | ◐ | ◐ | — |
| Ver la propia posición en lista | — | — | — | — | — | P |
| Crear o editar agendas | — | ◐ | — | — | — | — |
| Publicar, bloquear o suspender agendas | — | ◐ | — | — | ◐ | — |
| Ver agendas | ◐ | ◐ | ◐ | ◐ | ◐ | P |
| Crear oferta manual | — | ◐ | ◐ | — | — | — |
| Ver ofertas | ◐ | ◐ | ◐ | ◐ | ◐ | P |
| Aceptar o rechazar oferta | — | — | — | — | — | P |
| Confirmar reserva manual | — | ◐ | ◐ | — | — | — |
| Cancelar cita | — | ◐ | ◐ | — | ◐ | P |
| Registrar atención | — | — | — | — | ◐ | — |
| Registrar inasistencia | — | ◐ | ◐ | — | ◐ | — |
| Aprobar propuesta de reagendamiento | — | ◐ | ◐ | — | — | — |
| Rechazar propuesta de reagendamiento | — | ◐ | ◐ | — | — | — |
| Ver panel administrativo | ◐ | ◐ | ◐ | ◐ | ◐ | — |
| Ver reportes agregados | ✓ | ◐ | ◐ | ◐ | ◐ | — |
| Exportar reportes | ✓ | ◐ | ◐ | — | — | — |
| Ver notificaciones propias | — | — | — | — | — | P |
| Actualizar contactos y disponibilidad | — | — | — | — | — | P |
| Ver instrucciones administrativas | ◐ | ◐ | ◐ | ◐ | ◐ | P |

Notas:

- El administrador del sistema administra configuración y seguridad; no recibe por defecto acceso clínico. Si se le concede, debe ser un permiso explícito y auditado.
- El personal de SOME y admisión no ve diagnósticos ni notas clínicas.
- El profesional de salud y el médico especialista ven datos clínicos solo de pacientes relacionados con su trabajo.
- El paciente no ve notas internas, auditoría ni datos de otros pacientes.
- La aprobación de propuestas requiere permiso explícito; la prueba de “usuario sin permiso no aprueba” usa un rol que no lo tenga.

## 5. Protección de datos y privacidad

### Minimización

- Solo se guardan los datos necesarios para el proceso administrativo.
- Los datos clínicos van en tabla separada y no se copian a listados, reportes generales ni notificaciones.
- Los mensajes externos usan nombre, especialidad, fecha, hora, establecimiento y enlace al portal; sin diagnóstico.
- Los logs no incluyen cuerpos completos de solicitudes ni identificadores de salud.
- Las exportaciones incluyen solo columnas autorizadas.

### Datos personales

- Documento de identidad enmascarado en listados; visible completo solo con permiso.
- Teléfono y correo enmascarados cuando no se necesita contacto directo.
- Búsqueda por nombre con extensión `unaccent`; no se expone un listado masivo sin filtro.
- Prevención de enumeración: respuestas uniformes y límites de consulta.

### Retención y eliminación

- Pacientes y solicitudes con historia no se borran físicamente.
- Se desactivan o cierran; la eliminación definitiva requiere un procedimiento institucional aprobado.
- La auditoría se conserva según la política que defina la institución y la normativa aplicable.
- La tensión entre derecho de supresión y conservación de historia clínica/auditoría se resuelve con anonimización o restricción, no con borrado unilateral.
- Los plazos concretos están pendientes de validación legal.

### Copias de seguridad

- `pg_dump` programado en el entorno que corresponda.
- Cifrado en reposo y control de acceso al archivo.
- Prueba de restauración documentada.
- Prohibido usar datos reales en desarrollo.
- La política de retención, RPO y RTO está pendiente.

## 6. Amenazas y controles

| Amenaza | Control |
|---|---|
| Fuerza bruta | Límite de intentos, bloqueo temporal, auditoría. |
| Suplantación de paciente | Activación por funcionario, código de un solo uso, verificación de contacto. |
| IDOR / cambiar un ID en la URL | Filtrado por propietario y permiso en el servidor; pruebas automatizadas. |
| Escalada de privilegios | Permisos explícitos, roles mínimos, pruebas de denegación. |
| Doble reserva | Bloqueos, índices únicos parciales, revalidación. |
| Oferta duplicada | Clave idempotente y estado de la oferta. |
| Notificación duplicada | `dedupe_key` única. |
| Notificación falsa | Adaptador simulado; estado visible; no se afirma envío real. |
| Inyección SQL | ORM y consultas parametrizadas; sin SQL concatenado. |
| XSS | Autoescape de plantillas; evitar `safe`; sanitizar contenido enriquecido. |
| CSRF | Middleware y tokens en formularios; acciones por POST. |
| Fijación de sesión | Rotación al autenticar. |
| Borrado o edición de auditoría | Permisos de base de datos y disparador append-only. |
| Exportación maliciosa | Escape de fórmulas CSV, permisos y auditoría. |
| Enumeración de pacientes | Búsqueda autenticada, límites y respuestas uniformes. |
| Fuga por logs | Registros estructurados con IDs, no payloads sensibles. |
| Secuestro de enlace de oferta | Portal autenticado; token hasheado, único y con caducidad si se usa. |
| Abuso de cuenta interna | Mínimo privilegio, alcance por establecimiento, revisión de accesos. |

## 7. Requisitos legales y regulatorios a verificar

Esta lista es un punto de partida, no una asesoría jurídica ni una declaración de cumplimiento.

| Materia | Referencia a verificar | Implicancia |
|---|---|---|
| Protección de datos personales | Ley 19.628 y Ley 21.719, esta última con entrada en vigor prevista para diciembre de 2026; confirmar estado y textos en fuentes oficiales (BCN). | Bases de licitud, derechos, seguridad, brechas, delegado de protección de datos, evaluación de impacto. |
| Derechos de los pacientes | Ley 20.584. | Confidencialidad, consentimiento, acceso a ficha y tratamiento de datos de salud. |
| Documentos y firma electrónica | Ley 19.799, si se usan consentimientos o documentos electrónicos. | Valor probatorio y requisitos de firma. |
| Normativa sanitaria e interoperabilidad | Normas del MINSAL y del Servicio de Salud correspondiente. | Registros, plazos, codificación, intercambio de información. |
| Retención de información | Normativa sectorial y política institucional. | Plazo de conservación de ficha y auditoría. |
| Notificaciones y consentimiento | Ley 19.496 y normativa de datos, según canal. | Consentimiento, opt-in, horarios y baja. |
| Contratación de proveedores | Acuerdos de tratamiento de datos. | SMS, correo, WhatsApp y nube. |
| Seguridad de la información | Política institucional y estándares aplicables. | Roles, incidentes, continuidad, respaldo. |

Antes de usar datos reales se requiere:

1. Revisión jurídica.
2. Aprobación del comité de ética o instancia correspondiente, si aplica.
3. Evaluación de impacto en protección de datos.
4. Política de privacidad y consentimientos.
5. Definición de responsables y encargados.
6. Procedimiento de brechas.
7. Prueba de seguridad y análisis de riesgos.
8. Autorización institucional y plan de despliegue.

## 8. Controles técnicos mínimos para la Etapa 2

- `.env` fuera del repositorio; `.env.example` sin secretos.
- `DEBUG=False` por defecto en producción; `DEBUG=True` solo local.
- `SECRET_KEY` aleatoria y distinta por entorno.
- `ALLOWED_HOSTS` explícito.
- HTTPS y cookies seguras en producción.
- Usuario de base de datos con privilegios mínimos.
- Migraciones versionadas.
- Respaldos y restauración probados.
- Dependencias fijadas y revisión de vulnerabilidades.
- Análisis estático y formato con `ruff`.
- Pruebas de autenticación, autorización y CSRF.

## 9. Lo que no se afirmará

- No se afirmará que el sistema “cumple toda la normativa chilena”.
- No se afirmará que es “seguro para producción”.
- No se afirmará que un mensaje fue enviado realmente si solo se usó el adaptador simulado.
- No se afirmará que los indicadores son oficiales ni comparables con metas institucionales.
- No se afirmará que la priorización por antigüedad es clínicamente adecuada.
