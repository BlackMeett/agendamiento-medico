# Etapa 1 — Análisis y diseño

**Proyecto:** Sistema web de agendamiento médico de segundo nivel con reagendamiento automático.
**Estado:** Etapa 1 cerrada. La implementación de demostración está documentada en [`docs/etapa-2/README.md`](../etapa-2/README.md).
**Fecha:** 23 de octubre de 2026.
**Ubicación del proyecto:** `C:\Users\Usuario\proyectos\agendamiento-medico`

## Documentos de esta etapa

| Archivo | Contenido |
|---|---|
| `00-resumen-requisitos.md` | Problema, alcance, requisitos confirmados, supuestos y límites. |
| `01-arquitectura.md` | Alternativas tecnológicas, decisión, diagrama, carpetas y módulos. |
| `02-flujos-concurrencia.md` | Flujos operativos, estados y mecanismos contra asignaciones dobles. |
| `03-modelo-datos.md` | Modelo entidad-relación, entidades, claves, índices y restricciones. |
| `04-seguridad-permisos.md` | Seguridad, privacidad, normativa a verificar y matriz de permisos. |
| `05-historias-pruebas-ux.md` | Historias de usuario, criterios de aceptación, plan de pruebas y UX. |
| `06-plan-riesgos-decisiones.md` | Plan por etapas, riesgos, contradicciones y decisiones pendientes. |
| [`../etapa-2/README.md`](../etapa-2/README.md) | Implementación demo, verificación y limitaciones conocidas. |

## Decisión de arquitectura propuesta

Monolito modular con **Django 5.2 LTS + PostgreSQL 17 + plantillas Django + HTMX + Tailwind CSS**, ejecutado localmente. El motor de reglas y los servicios de dominio se mantienen separados de las vistas, con pruebas automatizadas y una cola transaccional de eventos y notificaciones.

> **Ajuste de implementación:** la demo se ejecutó con SQLite y plantillas Django con CSS propio, sin HTMX ni Tailwind, por las restricciones del entorno. PostgreSQL sigue siendo la recomendación para producción. Ver [`etapa-2`](../etapa-2/README.md).

## Cómo leer esta etapa

1. Revisar `00-resumen-requisitos.md` para confirmar alcance y supuestos.
2. Revisar `01-arquitectura.md` y `03-modelo-datos.md` para validar la base técnica.
3. Revisar `02-flujos-concurrencia.md` y `05-historias-pruebas-ux.md` para validar el comportamiento.
4. Revisar `04-seguridad-permisos.md` y `06-plan-riesgos-decisiones.md` antes de aprobar.
5. Revisar [`etapa-2`](../etapa-2/README.md) para el estado real de la demo y sus límites.

## Advertencia

Este diseño es académico. No constituye un sistema clínico certificado, no acredita cumplimiento legal y no debe usarse con datos reales de pacientes hasta completar las validaciones institucionales, jurídicas y de seguridad correspondientes.
