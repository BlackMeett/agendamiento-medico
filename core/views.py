from __future__ import annotations

import csv
import statistics
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from accounts.decorators import admin_requerido, funcionario_requerido
from accounts.models import PerfilUsuario
from core.helpers import resolver_alertas
from core.models import Alerta, EventoAuditoria, MensajeNotificacion
from core.notifications import despachar_pendientes
from core.scoping import (
    filtrar_agendas,
    filtrar_citas,
    filtrar_ofertas,
    filtrar_pacientes,
    filtrar_solicitudes,
    get_perfil,
)
from gestion.models import (
    Agenda,
    Cita,
    EventoMotor,
    HoraMedica,
    OfertaHora,
    Paciente,
    PropuestaReagendamiento,
    Solicitud,
)
from gestion.services import procesar_eventos_pendientes, vencer_ofertas


@login_required
def inicio(request):
    perfil = get_perfil(request.user)
    if perfil and perfil.rol == PerfilUsuario.Rol.PACIENTE:
        return redirect("portal_inicio")
    return redirect("dashboard")


@funcionario_requerido
def dashboard(request):
    perfil = get_perfil(request.user)
    solicitudes = filtrar_solicitudes(Solicitud.objects.all(), request.user)
    ofertas = filtrar_ofertas(OfertaHora.objects.all(), request.user)
    citas = filtrar_citas(Cita.objects.all(), request.user)
    agendas = filtrar_agendas(Agenda.objects.all(), request.user)
    pacientes = filtrar_pacientes(Paciente.objects.all(), request.user)

    contexto = {
        "titulo": "Panel de gestión",
        "total_pacientes": pacientes.count(),
        "total_lista": solicitudes.filter(
            estado__in=[Solicitud.Estado.EN_LISTA_ESPERA, Solicitud.Estado.OFERTA_PENDIENTE]
        ).count(),
        "ofertas_pendientes": ofertas.filter(estado=OfertaHora.Estado.PENDIENTE).count(),
        "citas_confirmadas": citas.filter(estado=Cita.Estado.CONFIRMADA).count(),
        "propuestas_pendientes": PropuestaReagendamiento.objects.filter(
            solicitud__in=solicitudes,
            estado=PropuestaReagendamiento.Estado.PENDIENTE,
        ).count(),
        "alertas": Alerta.objects.filter(estado=Alerta.Estado.ABIERTA).count(),
        "eventos_pendientes": EventoMotor.objects.filter(estado=EventoMotor.Estado.PENDIENTE).count(),
        "mensajes_pendientes": MensajeNotificacion.objects.filter(
            estado=MensajeNotificacion.Estado.PENDIENTE
        ).count(),
        "agendas_publicadas": agendas.filter(estado=Agenda.Estado.PUBLICADA).count(),
        "horas_disponibles": HoraMedica.objects.filter(
            estado=HoraMedica.Estado.DISPONIBLE,
            inicio__gt=timezone.now(),
            bloque__agenda__estado=Agenda.Estado.PUBLICADA,
            bloque__agenda__in=agendas,
        ).count(),
        "alertas_recientes": Alerta.objects.filter(estado=Alerta.Estado.ABIERTA)[:5],
        "proximas_citas": citas.filter(
            estado=Cita.Estado.CONFIRMADA, hora__inicio__gte=timezone.now()
        ).order_by("hora__inicio")[:5],
        "lista_reciente": solicitudes.filter(
            estado__in=[Solicitud.Estado.EN_LISTA_ESPERA, Solicitud.Estado.OFERTA_PENDIENTE]
        ).order_by("fecha_ingreso", "creado_en")[:5],
        "total_pendientes_sin_candidatos": Alerta.objects.filter(
            tipo=Alerta.Tipo.SIN_CANDIDATOS, estado=Alerta.Estado.ABIERTA
        ).count(),
    }
    if request.user.is_superuser or (perfil and perfil.rol == PerfilUsuario.Rol.ADMIN):
        contexto["actividad"] = EventoAuditoria.objects.all()[:8]
    else:
        contexto["actividad"] = EventoAuditoria.objects.filter(actor=request.user)[:8]
    return render(request, "core/dashboard.html", contexto)


@funcionario_requerido
def ejecutar_motor(request):
    if request.method != "POST":
        return redirect("dashboard")
    resultados = procesar_eventos_pendientes()
    vencidas = vencer_ofertas()
    despachados = despachar_pendientes()
    messages.success(
        request,
        f"Motor ejecutado: {resultados['procesados']} eventos, {vencidas} ofertas vencidas, "
        f"{despachados['procesados']} notificaciones simuladas.",
    )
    return redirect(request.META.get("HTTP_REFERER") or "dashboard")


@funcionario_requerido
def alertas(request):
    estado = request.GET.get("estado", "ABIERTA")
    qs = Alerta.objects.all()
    if estado:
        qs = qs.filter(estado=estado)
    paginator = Paginator(qs, 20)
    return render(
        request,
        "core/alertas.html",
        {
            "titulo": "Alertas operativas",
            "page_obj": paginator.get_page(request.GET.get("page")),
            "estado": estado,
            "estados": Alerta.Estado.choices,
        },
    )


@funcionario_requerido
def cerrar_alerta(request, pk):
    if request.method != "POST":
        return redirect("alertas")
    alerta = Alerta.objects.filter(pk=pk).first()
    if alerta:
        alerta.estado = Alerta.Estado.CERRADA
        alerta.resuelta_en = timezone.now()
        alerta.save(update_fields=["estado", "resuelta_en"])
        messages.success(request, "Alerta cerrada.")
    return redirect("alertas")


@funcionario_requerido
def auditoria(request):
    perfil = get_perfil(request.user)
    if not request.user.is_superuser and (perfil is None or perfil.rol != PerfilUsuario.Rol.ADMIN):
        from django.core.exceptions import PermissionDenied

        raise PermissionDenied("La auditoría completa requiere perfil administrador.")
    qs = EventoAuditoria.objects.all()
    q = request.GET.get("q", "").strip()
    accion = request.GET.get("accion", "").strip()
    if q:
        qs = qs.filter(
            Q(entidad__icontains=q)
            | Q(entidad_id__icontains=q)
            | Q(motivo__icontains=q)
            | Q(actor__username__icontains=q)
        )
    if accion:
        qs = qs.filter(accion=accion)
    acciones = EventoAuditoria.objects.values_list("accion", flat=True).distinct().order_by("accion")
    paginator = Paginator(qs, 30)
    return render(
        request,
        "core/auditoria.html",
        {
            "titulo": "Auditoría",
            "page_obj": paginator.get_page(request.GET.get("page")),
            "q": q,
            "accion": accion,
            "acciones": acciones,
        },
    )


@funcionario_requerido
def reportes(request):
    solicitudes = filtrar_solicitudes(Solicitud.objects.all(), request.user)
    hoy = timezone.localdate()
    activas = list(
        solicitudes.filter(
            estado__in=[Solicitud.Estado.EN_LISTA_ESPERA, Solicitud.Estado.OFERTA_PENDIENTE]
        ).select_related("especialidad", "paciente")
    )
    por_especialidad = (
        solicitudes.filter(
            estado__in=[Solicitud.Estado.EN_LISTA_ESPERA, Solicitud.Estado.OFERTA_PENDIENTE]
        )
        .values("especialidad__nombre")
        .annotate(total=Count("id"))
        .order_by("-total", "especialidad__nombre")
    )
    dias = [
        max((hoy - (s.fecha_lista_espera or s.fecha_ingreso)).days, 0) for s in activas
    ]
    ofertas = filtrar_ofertas(OfertaHora.objects.all(), request.user)
    citas = filtrar_citas(Cita.objects.all(), request.user)
    propuestas = PropuestaReagendamiento.objects.filter(solicitud__in=solicitudes)
    contexto = {
        "titulo": "Reportes e indicadores",
        "por_especialidad": por_especialidad,
        "total_activas": len(activas),
        "espera_promedio": round(statistics.mean(dias), 1) if dias else 0,
        "espera_mediana": round(statistics.median(dias), 1) if dias else 0,
        "espera_maxima": max(dias) if dias else 0,
        "ofertas_por_estado": ofertas.values("estado").annotate(total=Count("id")).order_by("estado"),
        "citas_por_estado": citas.values("estado").annotate(total=Count("id")).order_by("estado"),
        "propuestas_por_estado": propuestas.values("estado").annotate(total=Count("id")).order_by("estado"),
        "total_ofertas": ofertas.count(),
        "total_citas": citas.count(),
        "total_propuestas": propuestas.count(),
        "hoy": hoy,
    }
    return render(request, "core/reportes.html", contexto)


def _csv_seguro(valor):
    texto = "" if valor is None else str(valor)
    if texto.startswith(("=", "+", "-", "@")):
        return "'" + texto
    return texto


@funcionario_requerido
def exportar_reporte(request):
    solicitudes = filtrar_solicitudes(Solicitud.objects.all(), request.user)
    hoy = timezone.localdate()
    activas = solicitudes.filter(
        estado__in=[Solicitud.Estado.EN_LISTA_ESPERA, Solicitud.Estado.OFERTA_PENDIENTE]
    ).select_related("paciente", "especialidad")
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="lista_espera_demo.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(
        [
            "Solicitud UUID",
            "Paciente",
            "Documento enmascarado",
            "Especialidad",
            "Estado",
            "Fecha ingreso",
            "Fecha lista espera",
            "Días de espera",
        ]
    )
    for s in activas:
        writer.writerow(
            [
                _csv_seguro(s.uuid),
                _csv_seguro(s.paciente.nombre_completo),
                _csv_seguro(s.paciente.documento_enmascarado),
                _csv_seguro(s.especialidad.nombre),
                _csv_seguro(s.get_estado_display()),
                _csv_seguro(s.fecha_ingreso),
                _csv_seguro(s.fecha_lista_espera),
                _csv_seguro(max((hoy - (s.fecha_lista_espera or s.fecha_ingreso)).days, 0)),
            ]
        )
    from core.models import registrar_auditoria

    registrar_auditoria(
        actor=request.user,
        accion="REPORTE_EXPORTADO",
        entidad="Solicitud",
        entidad_id="lista_espera",
        motivo="Exportación CSV de lista de espera",
        request=request,
    )
    return response


def health(request):
    return JsonResponse({"status": "ok", "demo": True, "time": timezone.now().isoformat()})


@funcionario_requerido
def cerrar_alertas_hora(request):
    if request.method != "POST":
        return redirect("alertas")
    resolver_alertas(tipo="SIN_CANDIDATOS")
    messages.success(request, "Alertas de falta de candidatos cerradas.")
    return redirect("alertas")
