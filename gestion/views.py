from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import funcionario_requerido
from accounts.models import PerfilUsuario
from core.helpers import crear_alerta
from core.models import Alerta, registrar_auditoria
from core.scoping import (
    filtrar_agendas,
    filtrar_citas,
    filtrar_ofertas,
    filtrar_pacientes,
    filtrar_solicitudes,
    get_perfil,
    puede_ver_paciente,
    puede_ver_solicitud,
)
from core.notifications import despachar_pendientes

from . import services
from .forms import (
    AgendaForm,
    DatosClinicosForm,
    GenerarHorasForm,
    MotivoForm,
    PacienteForm,
    PreferenciaForm,
    SolicitudForm,
)
from .models import (
    Agenda,
    BloqueAgenda,
    Cita,
    DatosClinicosSolicitud,
    Especialidad,
    HoraMedica,
    OfertaHora,
    Paciente,
    PreferenciaDisponibilidad,
    PropuestaReagendamiento,
    Solicitud,
)


def _guardar_error(request, exc):
    messages.error(request, str(exc))


def _exigir_permiso(request, atributo, mensaje):
    perfil = get_perfil(request.user)
    if request.user.is_superuser:
        return
    if perfil is None or not getattr(perfil, atributo, False):
        raise PermissionDenied(mensaje)


def _paciente_scope(request, pk):
    paciente = get_object_or_404(Paciente, pk=pk)
    if not puede_ver_paciente(request.user, paciente):
        raise PermissionDenied("No tienes acceso a este paciente.")
    return paciente


def _solicitud_scope(request, uuid):
    solicitud = get_object_or_404(Solicitud, uuid=uuid)
    if not puede_ver_solicitud(request.user, solicitud):
        raise PermissionDenied("No tienes acceso a esta solicitud.")
    return solicitud


@funcionario_requerido
def pacientes_lista(request):
    qs = filtrar_pacientes(Paciente.objects.all(), request.user).select_related(
        "establecimiento_referencia"
    ).annotate(total_solicitudes=Count("solicitudes"))
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(nombres__icontains=q)
            | Q(apellidos__icontains=q)
            | Q(numero_documento__icontains=q)
            | Q(email__icontains=q)
        )
    paginator = Paginator(qs.order_by("apellidos", "nombres"), 20)
    return render(
        request,
        "gestion/pacientes_lista.html",
        {
            "titulo": "Pacientes",
            "page_obj": paginator.get_page(request.GET.get("page")),
            "q": q,
        },
    )


@funcionario_requerido
def paciente_nuevo(request):
    _exigir_permiso(request, "puede_gestionar_pacientes", "No tienes permiso para crear pacientes.")
    form = PacienteForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        paciente = form.save()
        registrar_auditoria(
            actor=request.user,
            accion="PACIENTE_CREADO",
            entidad="Paciente",
            entidad_id=paciente.uuid,
            despues={"documento": paciente.documento_enmascarado, "nombre": paciente.nombre_completo},
            request=request,
        )
        similares = Paciente.objects.filter(
            nombres__iexact=paciente.nombres, apellidos__iexact=paciente.apellidos
        ).exclude(pk=paciente.pk)
        if similares.exists():
            crear_alerta(
                tipo="DUPLICADO",
                mensaje=f"Posible duplicado de paciente: {paciente.nombre_completo}",
                entidad="Paciente",
                entidad_id=paciente.uuid,
                severidad="MEDIA",
            )
            messages.warning(request, "Se creó el paciente, pero hay nombres similares. Revisa posibles duplicados.")
        messages.success(request, "Paciente registrado.")
        return redirect("paciente_detalle", pk=paciente.pk)
    return render(
        request,
        "gestion/paciente_form.html",
        {"titulo": "Nuevo paciente", "form": form, "accion": "Registrar paciente"},
    )


@funcionario_requerido
def paciente_detalle(request, pk):
    paciente = _paciente_scope(request, pk)
    form_preferencia = PreferenciaForm()
    return render(
        request,
        "gestion/paciente_detalle.html",
        {
            "titulo": paciente.nombre_completo,
            "paciente": paciente,
            "solicitudes": paciente.solicitudes.select_related("especialidad").order_by("-fecha_ingreso"),
            "preferencias": paciente.preferencias.all(),
            "form_preferencia": form_preferencia,
        },
    )


@funcionario_requerido
def paciente_editar(request, pk):
    _exigir_permiso(request, "puede_gestionar_pacientes", "No tienes permiso para editar pacientes.")
    paciente = _paciente_scope(request, pk)
    form = PacienteForm(request.POST or None, instance=paciente, user=request.user)
    if request.method == "POST" and form.is_valid():
        antes = {"nombre": paciente.nombre_completo, "documento": paciente.documento_enmascarado}
        form.save()
        registrar_auditoria(
            actor=request.user,
            accion="PACIENTE_EDITADO",
            entidad="Paciente",
            entidad_id=paciente.uuid,
            antes=antes,
            despues={"nombre": paciente.nombre_completo},
            request=request,
        )
        messages.success(request, "Paciente actualizado.")
        return redirect("paciente_detalle", pk=paciente.pk)
    return render(
        request,
        "gestion/paciente_form.html",
        {"titulo": "Editar paciente", "form": form, "paciente": paciente, "accion": "Guardar cambios"},
    )


@require_POST
@funcionario_requerido
def preferencia_nueva(request, pk):
    _exigir_permiso(request, "puede_gestionar_pacientes", "No tienes permiso para modificar preferencias.")
    paciente = _paciente_scope(request, pk)
    form = PreferenciaForm(request.POST)
    if form.is_valid():
        preferencia = form.save(commit=False)
        preferencia.paciente = paciente
        preferencia.save()
        registrar_auditoria(
            actor=request.user,
            accion="PREFERENCIA_CREADA",
            entidad="Paciente",
            entidad_id=paciente.uuid,
            despues={"preferencia": str(preferencia)},
            request=request,
        )
        messages.success(request, "Preferencia de disponibilidad registrada.")
    else:
        messages.error(request, "Revisa los datos de la preferencia.")
    return redirect("paciente_detalle", pk=paciente.pk)


@require_POST
@funcionario_requerido
def preferencia_eliminar(request, pk, pref_pk):
    _exigir_permiso(request, "puede_gestionar_pacientes", "No tienes permiso para modificar preferencias.")
    paciente = _paciente_scope(request, pk)
    preferencia = get_object_or_404(PreferenciaDisponibilidad, pk=pref_pk, paciente=paciente)
    preferencia.delete()
    registrar_auditoria(
        actor=request.user,
        accion="PREFERENCIA_ELIMINADA",
        entidad="Paciente",
        entidad_id=paciente.uuid,
        motivo="Preferencia eliminada",
        request=request,
    )
    messages.success(request, "Preferencia eliminada.")
    return redirect("paciente_detalle", pk=paciente.pk)


@funcionario_requerido
def solicitudes_lista(request):
    qs = filtrar_solicitudes(Solicitud.objects.all(), request.user).select_related(
        "paciente", "especialidad", "establecimiento_origen"
    )
    estado = request.GET.get("estado", "").strip()
    q = request.GET.get("q", "").strip()
    if estado:
        qs = qs.filter(estado=estado)
    if q:
        qs = qs.filter(
            Q(paciente__nombres__icontains=q)
            | Q(paciente__apellidos__icontains=q)
            | Q(paciente__numero_documento__icontains=q)
            | Q(uuid__icontains=q)
        )
    paginator = Paginator(qs.order_by("-fecha_ingreso", "-creado_en"), 20)
    return render(
        request,
        "gestion/solicitudes_lista.html",
        {
            "titulo": "Solicitudes de atención",
            "page_obj": paginator.get_page(request.GET.get("page")),
            "estados": Solicitud.Estado.choices,
            "estado": estado,
            "q": q,
        },
    )


@funcionario_requerido
def solicitud_nueva(request):
    _exigir_permiso(request, "puede_gestionar_pacientes", "No tienes permiso para crear solicitudes.")
    initial = {}
    if request.GET.get("paciente"):
        initial["paciente"] = request.GET.get("paciente")
    form = SolicitudForm(request.POST or None, initial=initial, user=request.user)
    if request.method == "POST" and form.is_valid():
        solicitud = form.save(commit=False)
        solicitud.creada_por = request.user
        solicitud.estado = Solicitud.Estado.INGRESADA
        solicitud.save()
        registrar_auditoria(
            actor=request.user,
            accion="SOLICITUD_CREADA",
            entidad="Solicitud",
            entidad_id=solicitud.uuid,
            despues={
                "especialidad": solicitud.especialidad.nombre,
                "estado": solicitud.estado,
                "fecha_ingreso": str(solicitud.fecha_ingreso),
            },
            request=request,
        )
        duplicadas = Solicitud.objects.filter(
            paciente=solicitud.paciente,
            especialidad=solicitud.especialidad,
            estado__in=[
                Solicitud.Estado.EN_LISTA_ESPERA,
                Solicitud.Estado.OFERTA_PENDIENTE,
                Solicitud.Estado.AGENDADA,
            ],
        ).exclude(pk=solicitud.pk)
        if duplicadas.exists():
            crear_alerta(
                tipo="DUPLICADO",
                mensaje=f"Posible solicitud duplicada para {solicitud.paciente}.",
                entidad="Solicitud",
                entidad_id=solicitud.uuid,
                severidad="MEDIA",
            )
            messages.warning(request, "Existe otra solicitud activa del mismo paciente y especialidad.")
        messages.success(request, "Solicitud registrada. Revisa y valida para incorporarla a la lista.")
        return redirect("solicitud_detalle", uuid=solicitud.uuid)
    return render(
        request,
        "gestion/solicitud_form.html",
        {"titulo": "Nueva solicitud", "form": form, "accion": "Registrar solicitud"},
    )


@funcionario_requerido
def solicitud_detalle(request, uuid):
    solicitud = _solicitud_scope(request, uuid)
    perfil = get_perfil(request.user)
    puede_clinico = bool(perfil and perfil.puede_ver_clinico)
    return render(
        request,
        "gestion/solicitud_detalle.html",
        {
            "titulo": f"Solicitud {solicitud.short}",
            "solicitud": solicitud,
            "historial": solicitud.historial.select_related("actor")[:20],
            "ofertas": solicitud.ofertas.select_related("hora").order_by("-creado_en")[:10],
            "citas": solicitud.citas.select_related("hora").order_by("-hora__inicio"),
            "puede_clinico": puede_clinico,
            "datos_clinicos": getattr(solicitud, "datos_clinicos", None) if puede_clinico else None,
            "motivo_rechazo_form": MotivoForm(auto_id="id_rechazo_%s"),
            "motivo_cierre_form": MotivoForm(auto_id="id_cierre_%s"),
        },
    )


@require_POST
@funcionario_requerido
def solicitud_validar(request, uuid):
    _exigir_permiso(request, "puede_gestionar_pacientes", "No tienes permiso para validar solicitudes.")
    solicitud = _solicitud_scope(request, uuid)
    try:
        services.validar_solicitud(solicitud, actor=request.user, motivo="Validación administrativa")
        messages.success(request, "Solicitud validada e incorporada a la lista de espera.")
    except services.ErrorMotor as exc:
        _guardar_error(request, exc)
    return redirect("solicitud_detalle", uuid=solicitud.uuid)


@require_POST
@funcionario_requerido
def solicitud_rechazar(request, uuid):
    _exigir_permiso(request, "puede_gestionar_pacientes", "No tienes permiso para rechazar solicitudes.")
    solicitud = _solicitud_scope(request, uuid)
    form = MotivoForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Indica el motivo del rechazo.")
        return redirect("solicitud_detalle", uuid=solicitud.uuid)
    try:
        services.rechazar_solicitud(
            solicitud, actor=request.user, motivo=form.cleaned_data["motivo"]
        )
        messages.success(request, "Solicitud rechazada.")
    except services.ErrorMotor as exc:
        _guardar_error(request, exc)
    return redirect("solicitud_detalle", uuid=solicitud.uuid)


@require_POST
@funcionario_requerido
def solicitud_cerrar(request, uuid):
    _exigir_permiso(request, "puede_gestionar_pacientes", "No tienes permiso para cerrar solicitudes.")
    solicitud = _solicitud_scope(request, uuid)
    form = MotivoForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Indica el motivo del cierre.")
        return redirect("solicitud_detalle", uuid=solicitud.uuid)
    try:
        services.cerrar_solicitud(solicitud, actor=request.user, motivo=form.cleaned_data["motivo"])
        messages.success(request, "Solicitud cerrada.")
    except services.ErrorMotor as exc:
        _guardar_error(request, exc)
    return redirect("solicitud_detalle", uuid=solicitud.uuid)


@funcionario_requerido
def solicitud_datos_clinicos(request, uuid):
    solicitud = _solicitud_scope(request, uuid)
    perfil = get_perfil(request.user)
    if not perfil or not perfil.puede_ver_clinico:
        raise PermissionDenied("No tienes permiso para ver o editar datos clínicos.")
    datos, _ = DatosClinicosSolicitud.objects.get_or_create(solicitud=solicitud)
    form = DatosClinicosForm(request.POST or None, instance=datos)
    if request.method == "POST" and form.is_valid():
        datos = form.save(commit=False)
        datos.actualizado_por = request.user
        datos.save()
        registrar_auditoria(
            actor=request.user,
            accion="DATOS_CLINICOS_ACTUALIZADOS",
            entidad="Solicitud",
            entidad_id=solicitud.uuid,
            motivo="Actualización de datos clínicos restringidos",
            request=request,
        )
        messages.success(request, "Datos clínicos actualizados.")
        return redirect("solicitud_detalle", uuid=solicitud.uuid)
    return render(
        request,
        "gestion/datos_clinicos_form.html",
        {"titulo": "Datos clínicos restringidos", "form": form, "solicitud": solicitud},
    )


@funcionario_requerido
def lista_espera(request):
    qs = (
        filtrar_solicitudes(Solicitud.objects.all(), request.user)
        .filter(
            estado__in=[Solicitud.Estado.EN_LISTA_ESPERA, Solicitud.Estado.OFERTA_PENDIENTE]
        )
        .select_related("paciente", "especialidad", "establecimiento_origen", "establecimiento_destino")
        .annotate(
            ofertas_pendientes=Count(
                "ofertas", filter=Q(ofertas__estado=OfertaHora.Estado.PENDIENTE), distinct=True
            ),
            intentos=Count("ofertas", distinct=True),
        )
    )
    especialidad = request.GET.get("especialidad", "")
    q = request.GET.get("q", "").strip()
    con_oferta = request.GET.get("con_oferta", "")
    if especialidad:
        qs = qs.filter(especialidad_id=especialidad)
    if q:
        qs = qs.filter(
            Q(paciente__nombres__icontains=q)
            | Q(paciente__apellidos__icontains=q)
            | Q(paciente__numero_documento__icontains=q)
        )
    if con_oferta == "1":
        qs = qs.filter(ofertas_pendientes__gt=0)
    qs = qs.order_by("fecha_ingreso", "creado_en", "id")
    paginator = Paginator(qs, 25)
    return render(
        request,
        "gestion/lista_espera.html",
        {
            "titulo": "Lista de espera",
            "page_obj": paginator.get_page(request.GET.get("page")),
            "especialidades": Especialidad.objects.filter(activa=True),
            "especialidad": especialidad,
            "q": q,
            "con_oferta": con_oferta,
        },
    )


@funcionario_requerido
def agendas_lista(request):
    qs = filtrar_agendas(Agenda.objects.all(), request.user).select_related(
        "profesional", "establecimiento", "especialidad"
    )
    estado = request.GET.get("estado", "")
    if estado:
        qs = qs.filter(estado=estado)
    paginator = Paginator(qs.order_by("-fecha_inicio"), 20)
    return render(
        request,
        "gestion/agendas_lista.html",
        {
            "titulo": "Agendas médicas",
            "page_obj": paginator.get_page(request.GET.get("page")),
            "estados": Agenda.Estado.choices,
            "estado": estado,
        },
    )


@funcionario_requerido
def agenda_nueva(request):
    _exigir_permiso(request, "puede_gestionar_agendas", "No tienes permiso para crear agendas.")
    form = AgendaForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        agenda = form.save(commit=False)
        agenda.estado = Agenda.Estado.BORRADOR
        agenda.creada_por = request.user
        agenda.save()
        registrar_auditoria(
            actor=request.user,
            accion="AGENDA_CREADA",
            entidad="Agenda",
            entidad_id=agenda.pk,
            despues={"profesional": str(agenda.profesional), "estado": agenda.estado},
            request=request,
        )
        messages.success(request, "Agenda creada. Genera bloques y publícala.")
        return redirect("agenda_detalle", pk=agenda.pk)
    return render(
        request,
        "gestion/agenda_form.html",
        {"titulo": "Nueva agenda", "form": form, "accion": "Crear agenda"},
    )


@funcionario_requerido
def agenda_detalle(request, pk):
    agenda = get_object_or_404(
        filtrar_agendas(Agenda.objects.all(), request.user), pk=pk
    )
    bloques = agenda.bloques.prefetch_related("horas").order_by("fecha", "hora_inicio")
    return render(
        request,
        "gestion/agenda_detalle.html",
        {
            "titulo": f"Agenda {agenda.profesional}",
            "agenda": agenda,
            "bloques": bloques,
            "form_horas": GenerarHorasForm(),
            "motivo_form": MotivoForm(),
            "total_horas": HoraMedica.objects.filter(bloque__agenda=agenda).count(),
            "disponibles": HoraMedica.objects.filter(
                bloque__agenda=agenda, estado=HoraMedica.Estado.DISPONIBLE
            ).count(),
        },
    )


@require_POST
@funcionario_requerido
def agenda_generar(request, pk):
    _exigir_permiso(request, "puede_gestionar_agendas", "No tienes permiso para modificar agendas.")
    agenda = get_object_or_404(filtrar_agendas(Agenda.objects.all(), request.user), pk=pk)
    form = GenerarHorasForm(request.POST)
    if form.is_valid():
        try:
            creadas = services.generar_horas(
                agenda,
                dias_semana={int(d) for d in form.cleaned_data["dias_semana"]},
                hora_inicio=form.cleaned_data["hora_inicio"],
                hora_fin=form.cleaned_data["hora_fin"],
                actor=request.user,
            )
            messages.success(request, f"Se generaron {creadas} horas nuevas.")
        except services.ErrorMotor as exc:
            _guardar_error(request, exc)
    else:
        messages.error(request, "Revisa los parámetros de generación.")
    return redirect("agenda_detalle", pk=agenda.pk)


@require_POST
@funcionario_requerido
def agenda_publicar(request, pk):
    _exigir_permiso(request, "puede_gestionar_agendas", "No tienes permiso para publicar agendas.")
    agenda = get_object_or_404(filtrar_agendas(Agenda.objects.all(), request.user), pk=pk)
    try:
        services.publicar_agenda(agenda, actor=request.user)
        messages.success(request, "Agenda publicada. Sus horas ya pueden ofrecerse.")
    except services.ErrorMotor as exc:
        _guardar_error(request, exc)
    return redirect("agenda_detalle", pk=agenda.pk)


@require_POST
@funcionario_requerido
def agenda_suspender(request, pk):
    _exigir_permiso(request, "puede_gestionar_agendas", "No tienes permiso para suspender agendas.")
    agenda = get_object_or_404(filtrar_agendas(Agenda.objects.all(), request.user), pk=pk)
    form = MotivoForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Indica el motivo de la suspensión.")
        return redirect("agenda_detalle", pk=agenda.pk)
    try:
        resultado = services.suspender_agenda(
            agenda, actor=request.user, motivo=form.cleaned_data["motivo"]
        )
        messages.warning(
            request,
            f"Agenda suspendida. Propuestas creadas: {resultado['creadas']}; "
            f"sin alternativa: {resultado['sin_alternativa']}.",
        )
    except services.ErrorMotor as exc:
        _guardar_error(request, exc)
    return redirect("agenda_detalle", pk=agenda.pk)


@funcionario_requerido
def ofertas_lista(request):
    qs = filtrar_ofertas(OfertaHora.objects.all(), request.user).select_related(
        "solicitud__paciente", "solicitud__especialidad", "hora__bloque__agenda__profesional"
    )
    estado = request.GET.get("estado", "")
    if estado:
        qs = qs.filter(estado=estado)
    paginator = Paginator(qs.order_by("-creado_en"), 25)
    return render(
        request,
        "gestion/ofertas_lista.html",
        {
            "titulo": "Ofertas de hora",
            "page_obj": paginator.get_page(request.GET.get("page")),
            "estados": OfertaHora.Estado.choices,
            "estado": estado,
        },
    )


@funcionario_requerido
def oferta_detalle(request, pk):
    oferta = get_object_or_404(
        filtrar_ofertas(OfertaHora.objects.all(), request.user).select_related(
            "solicitud__paciente", "solicitud__especialidad", "hora__bloque__agenda__profesional"
        ),
        pk=pk,
    )
    return render(request, "gestion/oferta_detalle.html", {"titulo": "Detalle de oferta", "oferta": oferta})


@require_POST
@funcionario_requerido
def ofertas_vencer(request):
    cantidad = services.vencer_ofertas()
    messages.success(request, f"Se vencieron {cantidad} ofertas.")
    return redirect(request.META.get("HTTP_REFERER") or "ofertas_lista")


@funcionario_requerido
def propuestas_lista(request):
    solicitudes = filtrar_solicitudes(Solicitud.objects.all(), request.user)
    qs = PropuestaReagendamiento.objects.filter(solicitud__in=solicitudes).select_related(
        "solicitud__paciente", "solicitud__especialidad", "cita_original__hora", "hora_propuesta__bloque__agenda__profesional"
    )
    estado = request.GET.get("estado", "PENDIENTE_REVISION")
    if estado:
        qs = qs.filter(estado=estado)
    paginator = Paginator(qs.order_by("-creado_en"), 20)
    return render(
        request,
        "gestion/propuestas_lista.html",
        {
            "titulo": "Reagendamientos",
            "page_obj": paginator.get_page(request.GET.get("page")),
            "estados": PropuestaReagendamiento.Estado.choices,
            "estado": estado,
            "puede_aprobar": bool(
                get_perfil(request.user) and get_perfil(request.user).puede_aprobar_reagendamiento
            ),
        },
    )


@require_POST
@funcionario_requerido
def propuesta_aprobar(request, pk):
    perfil = get_perfil(request.user)
    if not perfil or not perfil.puede_aprobar_reagendamiento:
        raise PermissionDenied("No tienes permiso para aprobar propuestas de reagendamiento.")
    propuesta = get_object_or_404(
        PropuestaReagendamiento.objects.filter(
            solicitud__in=filtrar_solicitudes(Solicitud.objects.all(), request.user)
        ),
        pk=pk,
    )
    try:
        cita = services.aprobar_propuesta(propuesta.pk, actor=request.user, motivo="Aprobación humana")
        messages.success(request, f"Propuesta aprobada. Nueva cita: {cita.hora.inicio:%d/%m/%Y %H:%M}.")
    except services.ErrorMotor as exc:
        _guardar_error(request, exc)
    return redirect("propuestas_lista")


@require_POST
@funcionario_requerido
def propuesta_rechazar(request, pk):
    perfil = get_perfil(request.user)
    if not perfil or not perfil.puede_aprobar_reagendamiento:
        raise PermissionDenied("No tienes permiso para rechazar propuestas de reagendamiento.")
    propuesta = get_object_or_404(
        PropuestaReagendamiento.objects.filter(
            solicitud__in=filtrar_solicitudes(Solicitud.objects.all(), request.user)
        ),
        pk=pk,
    )
    form = MotivoForm(request.POST)
    motivo = form.cleaned_data["motivo"] if form.is_valid() else "Rechazo humano"
    try:
        services.rechazar_propuesta(propuesta.pk, actor=request.user, motivo=motivo)
        messages.success(request, "Propuesta rechazada; la solicitud vuelve a la lista de espera.")
    except services.ErrorMotor as exc:
        _guardar_error(request, exc)
    return redirect("propuestas_lista")


@funcionario_requerido
def cita_detalle(request, pk):
    cita = get_object_or_404(
        filtrar_citas(Cita.objects.all(), request.user).select_related(
            "solicitud__paciente", "solicitud__especialidad", "hora__bloque__agenda__profesional"
        ),
        pk=pk,
    )
    return render(
        request,
        "gestion/cita_detalle.html",
        {"titulo": "Detalle de cita", "cita": cita, "motivo_form": MotivoForm()},
    )


@require_POST
@funcionario_requerido
def cita_cancelar(request, pk):
    cita = get_object_or_404(filtrar_citas(Cita.objects.all(), request.user), pk=pk)
    form = MotivoForm(request.POST)
    motivo = form.cleaned_data["motivo"] if form.is_valid() else "Cancelación administrativa"
    try:
        services.cancelar_cita(cita.pk, actor=request.user, motivo=motivo, tipo="ESTABLECIMIENTO")
        messages.success(request, "Cita cancelada. La solicitud vuelve a evaluación.")
    except services.ErrorMotor as exc:
        _guardar_error(request, exc)
    return redirect("cita_detalle", pk=cita.pk)


@require_POST
@funcionario_requerido
def cita_atender(request, pk):
    cita = get_object_or_404(filtrar_citas(Cita.objects.all(), request.user), pk=pk)
    try:
        services.marcar_atendida(cita.pk, actor=request.user)
        messages.success(request, "Atención registrada.")
    except services.ErrorMotor as exc:
        _guardar_error(request, exc)
    return redirect("cita_detalle", pk=cita.pk)


@require_POST
@funcionario_requerido
def cita_inasistencia(request, pk):
    cita = get_object_or_404(filtrar_citas(Cita.objects.all(), request.user), pk=pk)
    try:
        services.registrar_inasistencia(cita.pk, actor=request.user)
        messages.warning(request, "Inasistencia registrada. La solicitud vuelve a la lista sin sanción automática.")
    except services.ErrorMotor as exc:
        _guardar_error(request, exc)
    return redirect("cita_detalle", pk=cita.pk)
