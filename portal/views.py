from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import paciente_requerido
from core.models import MensajeNotificacion
from core.notifications import marcar_leido
from gestion import services
from gestion.forms import PacientePerfilForm, PreferenciaForm
from gestion.models import Cita, OfertaHora, Paciente, PreferenciaDisponibilidad, Solicitud


def _paciente(request):
    paciente = Paciente.objects.filter(user=request.user, activo=True).first()
    if not paciente:
        raise PermissionDenied("Tu cuenta no está vinculada a una ficha de paciente.")
    return paciente


@paciente_requerido
def inicio(request):
    paciente = _paciente(request)
    ofertas = OfertaHora.objects.filter(
        solicitud__paciente=paciente, estado=OfertaHora.Estado.PENDIENTE
    ).select_related("solicitud__especialidad", "hora__bloque__agenda__profesional")
    citas = Cita.objects.filter(
        solicitud__paciente=paciente,
        estado=Cita.Estado.CONFIRMADA,
        hora__inicio__gte=timezone.now(),
    ).select_related("hora__bloque__agenda__profesional", "solicitud__especialidad")
    no_leidos = MensajeNotificacion.objects.filter(
        destinatario_tipo="PACIENTE",
        destinatario_id=str(paciente.uuid),
        estado__in=[MensajeNotificacion.Estado.PENDIENTE, MensajeNotificacion.Estado.SIMULADO],
    ).count()
    return render(
        request,
        "portal/inicio.html",
        {
            "titulo": "Mi portal",
            "paciente": paciente,
            "solicitudes": paciente.solicitudes.select_related("especialidad").order_by("-fecha_ingreso")[:5],
            "ofertas_pendientes": ofertas,
            "proximas_citas": citas[:5],
            "no_leidos": no_leidos,
        },
    )


@paciente_requerido
def solicitudes(request):
    paciente = _paciente(request)
    return render(
        request,
        "portal/solicitudes.html",
        {
            "titulo": "Mis solicitudes",
            "paciente": paciente,
            "solicitudes": paciente.solicitudes.select_related("especialidad").order_by("-fecha_ingreso"),
        },
    )


@paciente_requerido
def solicitud_detalle(request, uuid):
    paciente = _paciente(request)
    solicitud = get_object_or_404(
        Solicitud.objects.filter(paciente=paciente).select_related("especialidad"),
        uuid=uuid,
    )
    return render(
        request,
        "portal/solicitud_detalle.html",
        {
            "titulo": f"Solicitud {solicitud.short}",
            "paciente": paciente,
            "solicitud": solicitud,
            "ofertas": solicitud.ofertas.order_by("-creado_en")[:10],
            "citas": solicitud.citas.order_by("-hora__inicio"),
        },
    )


@paciente_requerido
def ofertas(request):
    paciente = _paciente(request)
    qs = (
        OfertaHora.objects.filter(solicitud__paciente=paciente)
        .select_related("solicitud__especialidad", "hora__bloque__agenda__profesional")
        .order_by("-creado_en")
    )
    return render(
        request,
        "portal/ofertas.html",
        {
            "titulo": "Mis ofertas de hora",
            "paciente": paciente,
            "ofertas": qs,
            "ahora": timezone.now(),
        },
    )


@require_POST
@paciente_requerido
def oferta_aceptar(request, pk):
    paciente = _paciente(request)
    oferta = get_object_or_404(
        OfertaHora.objects.filter(solicitud__paciente=paciente), pk=pk
    )
    try:
        cita = services.aceptar_oferta(oferta.pk, actor=request.user)
        messages.success(
            request,
            f"Hora confirmada para el {timezone.localtime(cita.hora.inicio):%d/%m/%Y a las %H:%M}.",
        )
        return redirect("portal_horas")
    except services.ErrorMotor as exc:
        messages.error(request, str(exc))
    return redirect("portal_ofertas")


@require_POST
@paciente_requerido
def oferta_rechazar(request, pk):
    paciente = _paciente(request)
    oferta = get_object_or_404(
        OfertaHora.objects.filter(solicitud__paciente=paciente), pk=pk
    )
    try:
        services.rechazar_oferta(oferta.pk, actor=request.user, motivo="Rechazo del paciente")
        messages.info(request, "Oferta rechazada. La hora será ofrecida a la siguiente persona.")
    except services.ErrorMotor as exc:
        messages.error(request, str(exc))
    return redirect("portal_ofertas")


@paciente_requerido
def horas(request):
    paciente = _paciente(request)
    citas = (
        Cita.objects.filter(solicitud__paciente=paciente)
        .select_related("hora__bloque__agenda__profesional", "solicitud__especialidad")
        .order_by("-hora__inicio")
    )
    return render(
        request,
        "portal/horas.html",
        {"titulo": "Mis horas", "paciente": paciente, "citas": citas},
    )


@require_POST
@paciente_requerido
def cita_cancelar(request, pk):
    paciente = _paciente(request)
    cita = get_object_or_404(Cita.objects.filter(solicitud__paciente=paciente), pk=pk)
    try:
        services.cancelar_cita(
            cita.pk,
            actor=request.user,
            motivo="Cancelación solicitada por el paciente",
            tipo="PACIENTE",
        )
        messages.success(request, "Cita cancelada. Tu solicitud vuelve a la lista de espera.")
    except services.ErrorMotor as exc:
        messages.error(request, str(exc))
    return redirect("portal_horas")


@paciente_requerido
def perfil(request):
    paciente = _paciente(request)
    form = PacientePerfilForm(request.POST or None, instance=paciente)
    form_pref = PreferenciaForm()
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Datos de contacto actualizados.")
        return redirect("portal_perfil")
    return render(
        request,
        "portal/perfil.html",
        {
            "titulo": "Mis datos",
            "paciente": paciente,
            "form": form,
            "form_pref": form_pref,
            "preferencias": paciente.preferencias.all(),
        },
    )


@require_POST
@paciente_requerido
def preferencia_nueva(request):
    paciente = _paciente(request)
    form = PreferenciaForm(request.POST)
    if form.is_valid():
        preferencia = form.save(commit=False)
        preferencia.paciente = paciente
        preferencia.save()
        messages.success(request, "Preferencia de disponibilidad agregada.")
    else:
        messages.error(request, "Revisa los datos de la preferencia.")
    return redirect("portal_perfil")


@require_POST
@paciente_requerido
def preferencia_eliminar(request, pk):
    paciente = _paciente(request)
    preferencia = get_object_or_404(PreferenciaDisponibilidad, pk=pk, paciente=paciente)
    preferencia.delete()
    messages.success(request, "Preferencia eliminada.")
    return redirect("portal_perfil")


@paciente_requerido
def notificaciones(request):
    paciente = _paciente(request)
    qs = MensajeNotificacion.objects.filter(
        destinatario_tipo="PACIENTE", destinatario_id=str(paciente.uuid)
    ).order_by("-creado_en")
    return render(
        request,
        "portal/notificaciones.html",
        {"titulo": "Notificaciones", "paciente": paciente, "mensajes": qs},
    )


@require_POST
@paciente_requerido
def notificacion_leer(request, pk):
    paciente = _paciente(request)
    mensaje = get_object_or_404(
        MensajeNotificacion,
        pk=pk,
        destinatario_tipo="PACIENTE",
        destinatario_id=str(paciente.uuid),
    )
    marcar_leido(mensaje)
    return redirect("portal_notificaciones")
