from __future__ import annotations

import csv
import statistics
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import admin_requerido, funcionario_requerido
from accounts.models import PerfilUsuario
from core.helpers import resolver_alertas
from core.models import Alerta, EventoAuditoria, MensajeNotificacion, registrar_auditoria
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
from gestion.services import (
    asignar_ofertas_disponibles,
    crear_recordatorios_proximos,
    procesar_eventos_pendientes,
    vencer_ofertas,
)


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
    ofertas = asignar_ofertas_disponibles()
    recordatorios = crear_recordatorios_proximos()
    despachados = despachar_pendientes()
    messages.success(
        request,
        f"Motor ejecutado: {resultados['procesados']} eventos, {vencidas} ofertas vencidas, "
        f"{ofertas} ofertas nuevas, {recordatorios} recordatorios creados y "
        f"{despachados['procesados']} notificaciones procesadas.",
    )
    return redirect(request.META.get("HTTP_REFERER") or "dashboard")


def _exigir_bandeja_notificaciones(request):
    if request.user.is_superuser:
        return
    perfil = get_perfil(request.user)
    if perfil is None or not perfil.puede_gestionar_pacientes:
        raise PermissionDenied("No tienes permiso para gestionar notificaciones.")


def _pacientes_visibles(request):
    qs = Paciente.objects.all()
    if request.user.is_superuser:
        return qs
    return filtrar_pacientes(qs, request.user)


def _notificaciones_scope(request):
    qs = MensajeNotificacion.objects.all()
    if request.user.is_superuser:
        return qs
    ids = [str(uuid) for uuid in _pacientes_visibles(request).values_list("uuid", flat=True)]
    return qs.filter(destinatario_tipo="PACIENTE", destinatario_id__in=ids)


def _destinatarios_visibles(request):
    if request.user.is_superuser:
        return None
    return list(
        _notificaciones_scope(request).values_list("destinatario_id", flat=True).distinct()
    )


@funcionario_requerido
def notificaciones_lista(request):
    _exigir_bandeja_notificaciones(request)
    qs = _notificaciones_scope(request).order_by("-creado_en")
    canal = request.GET.get("canal", "WHATSAPP").strip()
    estado = request.GET.get("estado", "").strip()
    if canal:
        qs = qs.filter(canal=canal)
    if estado:
        qs = qs.filter(estado=estado)

    resumen_whatsapp = {
        fila["estado"]: fila["total"]
        for fila in _notificaciones_scope(request)
        .filter(canal=MensajeNotificacion.Canal.WHATSAPP)
        .values("estado")
        .annotate(total=Count("id"))
    }
    paginator = Paginator(qs, 30)
    return render(
        request,
        "core/notificaciones.html",
        {
            "titulo": "Bandeja de notificaciones",
            "page_obj": paginator.get_page(request.GET.get("page")),
            "canal": canal,
            "estado": estado,
            "canales": MensajeNotificacion.Canal.choices,
            "estados": MensajeNotificacion.Estado.choices,
            "resumen_whatsapp": resumen_whatsapp,
            "modo_whatsapp": getattr(settings, "WHATSAPP_MODE", "SIMULADO"),
        },
    )


@require_POST
@funcionario_requerido
def notificaciones_despachar(request):
    _exigir_bandeja_notificaciones(request)
    resultado = despachar_pendientes(destinatario_ids=_destinatarios_visibles(request))
    registrar_auditoria(
        actor=request.user,
        accion="NOTIFICACIONES_DESPACHADAS",
        entidad="MensajeNotificacion",
        despues=resultado,
        request=request,
    )
    messages.success(
        request,
        f"Despacho ejecutado: {resultado['procesados']} procesados, "
        f"{resultado['fallidos']} con error y {resultado['pendientes']} pendientes.",
    )
    return redirect("notificaciones_lista")


@require_POST
@funcionario_requerido
def notificaciones_recordatorios(request):
    _exigir_bandeja_notificaciones(request)
    paciente_ids = None
    if not request.user.is_superuser:
        paciente_ids = list(_pacientes_visibles(request).values_list("pk", flat=True))
    creados = crear_recordatorios_proximos(paciente_ids=paciente_ids)
    resultado = despachar_pendientes(destinatario_ids=_destinatarios_visibles(request))
    registrar_auditoria(
        actor=request.user,
        accion="RECORDATORIOS_EJECUTADOS",
        entidad="Cita",
        despues={"creados": creados, **resultado},
        request=request,
    )
    messages.success(
        request,
        f"Recordatorios de 24 h: {creados} nuevos. "
        f"Despacho: {resultado['procesados']} procesados, {resultado['fallidos']} con error.",
    )
    return redirect("notificaciones_lista")


@require_POST
@funcionario_requerido
def notificacion_enviada_manual(request, pk):
    _exigir_bandeja_notificaciones(request)
    mensaje = get_object_or_404(
        _notificaciones_scope(request),
        pk=pk,
        canal=MensajeNotificacion.Canal.WHATSAPP,
    )
    if mensaje.estado == MensajeNotificacion.Estado.ENVIADO:
        messages.info(request, "Ese mensaje ya estaba marcado como enviado.")
        return redirect("notificaciones_lista")
    mensaje.estado = MensajeNotificacion.Estado.ENVIADO
    mensaje.proveedor_id = "MANUAL"
    mensaje.procesado_en = timezone.now()
    mensaje.error = ""
    mensaje.save(
        update_fields=["estado", "proveedor_id", "procesado_en", "error"]
    )
    registrar_auditoria(
        actor=request.user,
        accion="NOTIFICACION_ENVIADA_MANUAL",
        entidad="MensajeNotificacion",
        entidad_id=mensaje.pk,
        despues={"canal": mensaje.canal, "proveedor_id": mensaje.proveedor_id},
        request=request,
    )
    messages.success(request, "Mensaje marcado como enviado manualmente.")
    return redirect("notificaciones_lista")


@require_POST
@funcionario_requerido
def notificacion_reintentar(request, pk):
    _exigir_bandeja_notificaciones(request)
    mensaje = get_object_or_404(_notificaciones_scope(request), pk=pk)
    if mensaje.estado != MensajeNotificacion.Estado.FALLIDO:
        messages.info(request, "Solo se pueden reintentar mensajes fallidos.")
        return redirect("notificaciones_lista")
    mensaje.estado = MensajeNotificacion.Estado.PENDIENTE
    mensaje.intentos = 0
    mensaje.error = ""
    mensaje.proveedor_id = ""
    mensaje.procesado_en = None
    mensaje.save(
        update_fields=[
            "estado",
            "intentos",
            "error",
            "proveedor_id",
            "procesado_en",
        ]
    )
    registrar_auditoria(
        actor=request.user,
        accion="NOTIFICACION_REINTENTADA",
        entidad="MensajeNotificacion",
        entidad_id=mensaje.pk,
        despues={"canal": mensaje.canal},
        request=request,
    )
    messages.success(request, "Mensaje devuelto a la cola de envío.")
    return redirect("notificaciones_lista")


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
