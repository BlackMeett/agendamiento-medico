from __future__ import annotations

import threading
import uuid
from datetime import date as date_cls, datetime, time as time_cls, timedelta

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from core.helpers import crear_alerta, resolver_alertas
from core.models import MensajeNotificacion, Parametro, registrar_auditoria
from core.notifications import encolar_mensaje

from .models import (
    Agenda,
    BloqueAgenda,
    Cita,
    DatosClinicosSolicitud,
    EventoMotor,
    HistorialEstadoSolicitud,
    HoraMedica,
    OfertaHora,
    Paciente,
    PreferenciaDisponibilidad,
    PropuestaReagendamiento,
    Solicitud,
)

# SQLite serializa escrituras; este candado hace explícita la sección crítica
# dentro de un mismo proceso. En PostgreSQL se usaría SELECT ... FOR UPDATE.
_MOTOR_LOCK = threading.RLock()

TRANSICIONES = {
    Solicitud.Estado.INGRESADA: {
        Solicitud.Estado.PENDIENTE_REVISION,
        Solicitud.Estado.VALIDADA,
        Solicitud.Estado.RECHAZADA,
        Solicitud.Estado.CERRADA,
    },
    Solicitud.Estado.PENDIENTE_REVISION: {
        Solicitud.Estado.VALIDADA,
        Solicitud.Estado.RECHAZADA,
        Solicitud.Estado.CERRADA,
    },
    Solicitud.Estado.VALIDADA: {
        Solicitud.Estado.EN_LISTA_ESPERA,
        Solicitud.Estado.CERRADA,
    },
    Solicitud.Estado.EN_LISTA_ESPERA: {
        Solicitud.Estado.OFERTA_PENDIENTE,
        Solicitud.Estado.AGENDADA,
        Solicitud.Estado.CANCELADA,
        Solicitud.Estado.CERRADA,
    },
    Solicitud.Estado.OFERTA_PENDIENTE: {
        Solicitud.Estado.EN_LISTA_ESPERA,
        Solicitud.Estado.AGENDADA,
        Solicitud.Estado.CANCELADA,
        Solicitud.Estado.CERRADA,
    },
    Solicitud.Estado.AGENDADA: {
        Solicitud.Estado.ATENDIDA,
        Solicitud.Estado.EN_LISTA_ESPERA,
        Solicitud.Estado.CANCELADA,
        Solicitud.Estado.CERRADA,
    },
    Solicitud.Estado.ATENDIDA: set(),
    Solicitud.Estado.RECHAZADA: set(),
    Solicitud.Estado.CANCELADA: set(),
    Solicitud.Estado.CERRADA: set(),
}


class ErrorMotor(Exception):
    """Error de negocio controlado por el motor."""


def ahora():
    return timezone.now()


def nuevo_id():
    return uuid.uuid4()


def transicionar_solicitud(
    solicitud: Solicitud,
    nuevo_estado: str,
    *,
    actor=None,
    motivo: str = "",
    correlation=None,
    actor_tipo: str = "USUARIO",
):
    anterior = solicitud.estado
    permitidos = TRANSICIONES.get(anterior, set())
    if nuevo_estado not in permitidos:
        raise ErrorMotor(f"Transición inválida: {anterior} → {nuevo_estado}")
    solicitud.estado = nuevo_estado
    if nuevo_estado == Solicitud.Estado.EN_LISTA_ESPERA and not solicitud.fecha_lista_espera:
        solicitud.fecha_lista_espera = timezone.localdate()
    solicitud.save(update_fields=["estado", "fecha_lista_espera", "actualizado_en"])
    HistorialEstadoSolicitud.objects.create(
        solicitud=solicitud,
        estado_anterior=anterior,
        estado_nuevo=nuevo_estado,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        actor_tipo=actor_tipo,
        motivo=motivo,
        correlation_id=correlation or uuid.uuid4(),
    )
    registrar_auditoria(
        actor=actor,
        actor_tipo=actor_tipo,
        accion="TRANSICION_SOLICITUD",
        entidad="Solicitud",
        entidad_id=solicitud.uuid,
        antes={"estado": anterior},
        despues={"estado": nuevo_estado},
        motivo=motivo,
        correlation_id=correlation,
    )
    return solicitud


def validar_solicitud(solicitud: Solicitud, *, actor=None, motivo="Validación administrativa", correlation=None):
    with transaction.atomic():
        if solicitud.estado not in {Solicitud.Estado.INGRESADA, Solicitud.Estado.PENDIENTE_REVISION}:
            raise ErrorMotor("Solo se puede validar una solicitud ingresada o pendiente de revisión.")
        solicitud.fecha_validacion = timezone.localdate()
        solicitud.save(update_fields=["fecha_validacion", "actualizado_en"])
        transicionar_solicitud(
            solicitud,
            Solicitud.Estado.VALIDADA,
            actor=actor,
            motivo=motivo,
            correlation=correlation,
        )
        transicionar_solicitud(
            solicitud,
            Solicitud.Estado.EN_LISTA_ESPERA,
            actor=actor,
            motivo="Ingreso a lista de espera",
            correlation=correlation,
        )
    return solicitud


def _crear_solicitud_portal_base(
    *,
    paciente: Paciente,
    especialidad,
    observaciones="",
    modo_asignacion="AUTOMATICO",
    actor=None,
    correlation=None,
):
    """Crea y valida una solicitud del portal. El llamador abre la transacción."""
    estados_activos = {
        Solicitud.Estado.INGRESADA,
        Solicitud.Estado.PENDIENTE_REVISION,
        Solicitud.Estado.VALIDADA,
        Solicitud.Estado.EN_LISTA_ESPERA,
        Solicitud.Estado.OFERTA_PENDIENTE,
        Solicitud.Estado.AGENDADA,
    }
    if not paciente.activo:
        raise ErrorMotor("La ficha del paciente no está activa.")
    if Solicitud.objects.filter(
        paciente=paciente,
        especialidad=especialidad,
        estado__in=estados_activos,
    ).exists():
        raise ErrorMotor("Ya tienes una solicitud activa para esta especialidad.")

    solicitud = Solicitud.objects.create(
        paciente=paciente,
        especialidad=especialidad,
        establecimiento_origen=paciente.establecimiento_referencia,
        establecimiento_destino=None,
        origen=Solicitud.Origen.PORTAL,
        estado=Solicitud.Estado.INGRESADA,
        fecha_ingreso=timezone.localdate(),
        observaciones=(observaciones or "").strip(),
        creada_por=actor,
    )
    registrar_auditoria(
        actor=actor,
        accion="SOLICITUD_PORTAL_CREADA",
        entidad="Solicitud",
        entidad_id=solicitud.uuid,
        despues={
            "especialidad": especialidad.nombre,
            "origen": Solicitud.Origen.PORTAL,
            "estado": Solicitud.Estado.INGRESADA,
            "modo_asignacion": modo_asignacion,
        },
        correlation_id=correlation,
    )
    validar_solicitud(
        solicitud,
        actor=actor,
        motivo="Solicitud creada desde el portal del paciente",
        correlation=correlation,
    )
    return solicitud


def crear_solicitud_portal(
    *,
    paciente: Paciente,
    especialidad,
    observaciones="",
    actor=None,
    correlation=None,
):
    """Registra una solicitud creada por el paciente y busca una oferta compatible.

    La solicitud se incorpora a la lista de espera sin asignar prioridad clínica.
    Si no hay una hora disponible, queda activa para futuras ejecuciones del motor.
    """
    with _MOTOR_LOCK, transaction.atomic():
        solicitud = _crear_solicitud_portal_base(
            paciente=paciente,
            especialidad=especialidad,
            observaciones=observaciones,
            modo_asignacion="AUTOMATICO",
            actor=actor,
            correlation=correlation,
        )
        oferta = _intentar_oferta_para_solicitud(
            solicitud, actor=actor, correlation=correlation
        )
    return solicitud, oferta


def crear_solicitud_portal_manual(
    *,
    paciente: Paciente,
    especialidad,
    hora: HoraMedica,
    observaciones="",
    actor=None,
    correlation=None,
):
    """Crea una solicitud y reserva directamente la hora elegida por el paciente.

    La reserva revalida la especialidad, la agenda, el estado de la hora y
    las citas superpuestas del paciente dentro de la misma sección crítica.
    """
    with _MOTOR_LOCK, transaction.atomic():
        solicitud = _crear_solicitud_portal_base(
            paciente=paciente,
            especialidad=especialidad,
            observaciones=observaciones,
            modo_asignacion="MANUAL",
            actor=actor,
            correlation=correlation,
        )
        cita = crear_cita_manual(
            solicitud,
            hora,
            actor=actor,
            correlation=correlation,
            motivo="Reserva directa de hora desde el portal",
            accion="CITA_RESERVADA_PORTAL",
            notificar=True,
        )
    return solicitud, cita


def rechazar_solicitud(solicitud: Solicitud, *, actor=None, motivo="", correlation=None):
    if not motivo:
        raise ErrorMotor("El motivo de rechazo es obligatorio.")
    with transaction.atomic():
        transicionar_solicitud(
            solicitud,
            Solicitud.Estado.RECHAZADA,
            actor=actor,
            motivo=motivo,
            correlation=correlation,
        )
        solicitud.motivo_cierre = motivo
        solicitud.save(update_fields=["motivo_cierre", "actualizado_en"])
        _mensaje_paciente(
            solicitud.paciente,
            dedupe_key=f"solicitud:{solicitud.uuid}:rechazada",
            asunto="Tu solicitud fue rechazada",
            cuerpo=(
                f"Tu solicitud de {solicitud.especialidad.nombre} fue rechazada. "
                f"Motivo: {motivo}. Si necesitas más información, contacta al establecimiento."
            ),
            correlation=correlation,
        )
    return solicitud


def cerrar_solicitud(solicitud: Solicitud, *, actor=None, motivo="Cierre administrativo", correlation=None):
    if not motivo:
        raise ErrorMotor("El motivo de cierre es obligatorio.")
    with transaction.atomic():
        if solicitud.estado == Solicitud.Estado.AGENDADA:
            raise ErrorMotor("Cancela o resuelve la cita antes de cerrar la solicitud.")
        transicionar_solicitud(
            solicitud,
            Solicitud.Estado.CERRADA,
            actor=actor,
            motivo=motivo,
            correlation=correlation,
        )
        solicitud.motivo_cierre = motivo
        solicitud.save(update_fields=["motivo_cierre", "actualizado_en"])
    return solicitud


def crear_evento(
    *,
    tipo: str,
    entidad_tipo: str,
    entidad_id,
    idempotency_key: str,
    payload: dict | None = None,
    correlation=None,
):
    evento, creado = EventoMotor.objects.get_or_create(
        idempotency_key=idempotency_key,
        defaults={
            "tipo": tipo,
            "entidad_tipo": entidad_tipo,
            "entidad_id": str(entidad_id),
            "payload": payload or {},
            "correlation_id": correlation or uuid.uuid4(),
        },
    )
    if creado:
        registrar_auditoria(
            actor_tipo="SISTEMA",
            accion="EVENTO_CREADO",
            entidad=entidad_tipo,
            entidad_id=entidad_id,
            despues={"tipo": tipo, "idempotency_key": idempotency_key},
            correlation_id=correlation,
        )
    return evento


def procesar_evento(evento: EventoMotor):
    if evento.estado == EventoMotor.Estado.COMPLETADO:
        return evento
    fallo = None
    with _MOTOR_LOCK, transaction.atomic():
        evento = EventoMotor.objects.select_for_update().get(pk=evento.pk)
        if evento.estado == EventoMotor.Estado.COMPLETADO:
            return evento
        evento.estado = EventoMotor.Estado.PROCESANDO
        evento.intentos += 1
        evento.save(update_fields=["estado", "intentos", "actualizado_en"])
        try:
            if evento.tipo == "HORA_LIBERADA":
                ofrecer_hora(int(evento.entidad_id), correlation=evento.correlation_id, actor_tipo="SISTEMA")
            elif evento.tipo == "AGENDA_SUSPENDIDA":
                generar_propuestas_agenda(
                    int(evento.entidad_id),
                    motivo="Agenda suspendida",
                    correlation=evento.correlation_id,
                )
            evento.estado = EventoMotor.Estado.COMPLETADO
            evento.procesado_en = timezone.now()
            evento.error = ""
            evento.save(update_fields=["estado", "procesado_en", "error", "actualizado_en"])
        except Exception as exc:
            evento.estado = EventoMotor.Estado.FALLIDO
            evento.error = str(exc)[:255]
            evento.save(update_fields=["estado", "error", "actualizado_en"])
            crear_alerta(
                tipo="AGENDA_SUSPENDIDA",
                mensaje=f"Error al procesar evento {evento.tipo}: {exc}",
                entidad="EventoMotor",
                entidad_id=evento.pk,
                severidad="ALTA",
            )
            fallo = exc
    if fallo is not None:
        raise fallo
    return evento


def procesar_eventos_pendientes(limite=50):
    eventos = list(
        EventoMotor.objects.filter(estado=EventoMotor.Estado.PENDIENTE).order_by("creado_en")[:limite]
    )
    resultados = {"procesados": 0, "fallidos": 0}
    for evento in eventos:
        try:
            procesar_evento(evento)
            resultados["procesados"] += 1
        except Exception:
            resultados["fallidos"] += 1
    return resultados


def _mensaje_paciente(
    paciente: Paciente,
    *,
    dedupe_key: str,
    asunto: str,
    cuerpo: str,
    correlation=None,
    incluir_externo=True,
):
    mensaje_portal, _ = encolar_mensaje(
        dedupe_key=f"{dedupe_key}:PORTAL",
        destinatario_tipo="PACIENTE",
        destinatario_id=paciente.uuid,
        destinatario_nombre=paciente.nombre_completo,
        destinatario_contacto="Portal del paciente",
        canal="PORTAL",
        asunto=asunto,
        cuerpo=cuerpo,
        correlation_id=correlation,
    )
    if incluir_externo and paciente.consentimiento_notificaciones:
        canal = paciente.canal_preferido
        contacto = paciente.email if canal == "EMAIL" else paciente.telefono
        if canal != "PORTAL" and contacto:
            encolar_mensaje(
                dedupe_key=f"{dedupe_key}:{canal}",
                destinatario_tipo="PACIENTE",
                destinatario_id=paciente.uuid,
                destinatario_nombre=paciente.nombre_completo,
                destinatario_contacto=contacto,
                canal=canal,
                asunto=asunto,
                cuerpo=cuerpo,
                correlation_id=correlation,
            )
    return mensaje_portal


def crear_recordatorios_proximos(
    *, ahora_ref=None, ventana_horas=24, correlation=None, paciente_ids=None
):
    """Encola recordatorios para citas confirmadas dentro de la ventana.

    La tarea es idempotente: usa una dedupe_key por cita. En producción debe
    ejecutarse periódicamente (por ejemplo, cada hora); en la demo se puede
    lanzar desde la bandeja de notificaciones o con el comando
    ``manage.py recordatorios``.
    """
    ahora_ref = ahora_ref or timezone.now()
    limite = ahora_ref + timedelta(hours=ventana_horas)
    citas = (
        Cita.objects.filter(
            estado=Cita.Estado.CONFIRMADA,
            hora__inicio__gte=ahora_ref,
            hora__inicio__lte=limite,
        )
        .select_related(
            "solicitud__paciente",
            "solicitud__especialidad",
            "hora__bloque__agenda__profesional",
        )
        .order_by("hora__inicio", "pk")
    )
    if paciente_ids is not None:
        citas = citas.filter(solicitud__paciente_id__in=paciente_ids)
    creados = 0
    for cita in citas:
        dedupe_portal = f"cita:{cita.uuid}:recordatorio24h:PORTAL"
        ya_existia = MensajeNotificacion.objects.filter(dedupe_key=dedupe_portal).exists()
        _mensaje_paciente(
            cita.solicitud.paciente,
            dedupe_key=f"cita:{cita.uuid}:recordatorio24h",
            asunto="Recordatorio de tu hora",
            cuerpo=(
                f"Te recordamos tu hora de {cita.solicitud.especialidad.nombre} el "
                f"{timezone.localtime(cita.hora.inicio):%d/%m/%Y a las %H:%M} "
                f"con {cita.hora.bloque.agenda.profesional}. "
                "Si no puedes asistir, cancela desde el portal."
            ),
            correlation=correlation or cita.correlation_id,
        )
        if not ya_existia:
            creados += 1
    if creados:
        registrar_auditoria(
            actor_tipo="SISTEMA",
            accion="RECORDATORIOS_CREADOS",
            entidad="Cita",
            entidad_id="",
            despues={"creados": creados, "ventana_horas": ventana_horas},
            correlation_id=correlation,
        )
    return creados


def _candidatos_para_hora(hora: HoraMedica, excluir_ids=None):
    agenda = hora.bloque.agenda
    qs = (
        Solicitud.objects.filter(
            estado=Solicitud.Estado.EN_LISTA_ESPERA,
            especialidad=agenda.especialidad,
        )
        .filter(Q(establecimiento_destino__isnull=True) | Q(establecimiento_destino=agenda.establecimiento))
        .exclude(ofertas__estado=OfertaHora.Estado.PENDIENTE)
        .exclude(citas__estado__in=[Cita.Estado.CONFIRMADA, Cita.Estado.ATENDIDA])
        .exclude(
            ofertas__hora=hora,
            ofertas__estado__in=[OfertaHora.Estado.RECHAZADA, OfertaHora.Estado.VENCIDA],
        )
        .select_related("paciente", "especialidad", "establecimiento_destino")
        .order_by("fecha_ingreso", "creado_en", "id")
    )
    if excluir_ids:
        qs = qs.exclude(id__in=excluir_ids)

    # Un paciente no debe tener dos ofertas pendientes ni una cita superpuesta.
    pacientes_con_oferta = set(
        OfertaHora.objects.filter(estado=OfertaHora.Estado.PENDIENTE).values_list(
            "solicitud__paciente_id", flat=True
        )
    )
    pacientes_con_cita = set(
        Cita.objects.filter(
            estado__in=[Cita.Estado.CONFIRMADA, Cita.Estado.ATENDIDA],
            hora__inicio__lt=hora.fin,
            hora__fin__gt=hora.inicio,
        ).values_list("solicitud__paciente_id", flat=True)
    )
    excluidos = pacientes_con_oferta | pacientes_con_cita
    if excluidos:
        qs = qs.exclude(paciente_id__in=excluidos)

    candidatos = []
    inicio_local = timezone.localtime(hora.inicio)
    for solicitud in qs:
        restricciones = PreferenciaDisponibilidad.objects.filter(
            paciente=solicitud.paciente, vigente=True, es_restriccion=True
        )
        if restricciones.exists():
            coincide = any(
                p.dia_semana == inicio_local.weekday()
                and p.hora_desde <= inicio_local.time() < p.hora_hasta
                for p in restricciones
            )
            if not coincide:
                continue
        candidatos.append(solicitud)
    return candidatos


def ofrecer_hora(hora_id: int, *, correlation=None, actor=None, actor_tipo="SISTEMA"):
    with _MOTOR_LOCK, transaction.atomic():
        try:
            hora = (
                HoraMedica.objects.select_related("bloque__agenda__establecimiento", "bloque__agenda__especialidad")
                .select_for_update()
                .get(pk=hora_id)
            )
        except HoraMedica.DoesNotExist:
            raise ErrorMotor("La hora no existe.")
        if not hora.disponible:
            raise ErrorMotor("La hora ya no está disponible.")
        if hora.estado != HoraMedica.Estado.DISPONIBLE:
            raise ErrorMotor("La hora no está en estado disponible.")

        candidatos = _candidatos_para_hora(hora)
        if not candidatos:
            crear_alerta(
                tipo="SIN_CANDIDATOS",
                mensaje=f"No hay solicitudes compatibles para la hora {hora.inicio:%d/%m/%Y %H:%M}.",
                entidad="HoraMedica",
                entidad_id=hora.pk,
                severidad="MEDIA",
                correlation=correlation,
            )
            return None

        solicitud = candidatos[0]
        intento = OfertaHora.objects.filter(solicitud=solicitud, hora=hora).count() + 1
        idempotency_key = f"oferta:{hora.pk}:{solicitud.pk}:{intento}"
        horas_vigencia = Parametro.get_int("oferta.vigencia_horas", 48)
        expira_en = timezone.now() + timedelta(hours=horas_vigencia)
        try:
            with transaction.atomic():
                oferta = OfertaHora.objects.create(
                    solicitud=solicitud,
                    hora=hora,
                    estado=OfertaHora.Estado.PENDIENTE,
                    canal=solicitud.paciente.canal_preferido,
                    expira_en=expira_en,
                    intento=intento,
                    idempotency_key=idempotency_key,
                    creada_por_sistema=actor is None,
                    creada_por=actor,
                    correlation_id=correlation or uuid.uuid4(),
                )
        except IntegrityError:
            existente = OfertaHora.objects.filter(
                hora=hora, estado=OfertaHora.Estado.PENDIENTE
            ).first()
            if existente:
                return existente
            raise ErrorMotor("No fue posible crear la oferta por un conflicto de concurrencia.")

        hora.estado = HoraMedica.Estado.OFRECIDA
        hora.version += 1
        hora.save(update_fields=["estado", "version", "actualizado_en"])
        transicionar_solicitud(
            solicitud,
            Solicitud.Estado.OFERTA_PENDIENTE,
            actor=actor,
            actor_tipo=actor_tipo,
            motivo="Oferta de hora generada por el motor",
            correlation=correlation,
        )
        _mensaje_paciente(
            solicitud.paciente,
            dedupe_key=f"oferta:{oferta.uuid}:creada",
            asunto="Tienes una nueva oferta de hora",
            cuerpo=(
                f"Hola {solicitud.paciente.nombres}, hay una hora disponible de "
                f"{solicitud.especialidad.nombre} el "
                f"{timezone.localtime(hora.inicio):%d/%m/%Y a las %H:%M}. "
                "Ingresa al portal para aceptarla o rechazarla dentro del plazo."
            ),
            correlation=oferta.correlation_id,
        )
        registrar_auditoria(
            actor=actor,
            actor_tipo=actor_tipo,
            accion="OFERTA_CREADA",
            entidad="OfertaHora",
            entidad_id=oferta.uuid,
            despues={
                "hora": hora.pk,
                "solicitud": str(solicitud.uuid),
                "expira_en": expira_en.isoformat(),
            },
            correlation_id=oferta.correlation_id,
        )
        resolver_alertas(tipo="SIN_CANDIDATOS", entidad="HoraMedica", entidad_id=hora.pk)
        return oferta


def horas_disponibles_para_especialidad(especialidad):
    """Horas que el paciente puede elegir manualmente para una especialidad."""
    return (
        HoraMedica.objects.filter(
            estado=HoraMedica.Estado.DISPONIBLE,
            inicio__gt=timezone.now(),
            bloque__estado=BloqueAgenda.Estado.DISPONIBLE,
            bloque__agenda__estado=Agenda.Estado.PUBLICADA,
            bloque__agenda__especialidad=especialidad,
        )
        .select_related(
            "bloque__agenda__especialidad",
            "bloque__agenda__profesional",
            "bloque__agenda__establecimiento",
        )
        .order_by(
            "inicio",
            "bloque__agenda__profesional__apellidos",
            "bloque__agenda__profesional__nombres",
            "pk",
        )
    )


def _horas_disponibles_para_solicitud(solicitud: Solicitud):
    qs = HoraMedica.objects.filter(
        estado=HoraMedica.Estado.DISPONIBLE,
        inicio__gt=timezone.now(),
        bloque__estado=BloqueAgenda.Estado.DISPONIBLE,
        bloque__agenda__estado=Agenda.Estado.PUBLICADA,
        bloque__agenda__especialidad_id=solicitud.especialidad_id,
    )
    if solicitud.establecimiento_destino_id:
        qs = qs.filter(
            bloque__agenda__establecimiento_id=solicitud.establecimiento_destino_id
        )
    return qs.select_related("bloque__agenda").order_by("inicio")


def _intentar_oferta_para_solicitud(solicitud: Solicitud, *, actor=None, correlation=None):
    """Intenta ofrecer la primera hora compatible respetando el orden de llegada."""
    for hora in _horas_disponibles_para_solicitud(solicitud)[:25]:
        candidatos = _candidatos_para_hora(hora)
        if not candidatos or candidatos[0].pk != solicitud.pk:
            continue
        try:
            oferta = ofrecer_hora(
                hora.pk,
                actor=actor,
                actor_tipo="USUARIO",
                correlation=correlation,
            )
        except ErrorMotor:
            continue
        if oferta and oferta.solicitud_id == solicitud.pk:
            return oferta
    return None


def asignar_ofertas_disponibles(limite=25):
    """Busca horas disponibles y genera ofertas para las solicitudes en espera."""
    creadas = 0
    with _MOTOR_LOCK:
        horas = list(
            HoraMedica.objects.filter(
                estado=HoraMedica.Estado.DISPONIBLE,
                inicio__gt=timezone.now(),
                bloque__estado=BloqueAgenda.Estado.DISPONIBLE,
                bloque__agenda__estado=Agenda.Estado.PUBLICADA,
            )
            .select_related("bloque__agenda")
            .order_by("inicio")[:limite]
        )
        for hora in horas:
            if not _candidatos_para_hora(hora):
                continue
            try:
                oferta = ofrecer_hora(hora.pk, actor_tipo="SISTEMA")
            except ErrorMotor:
                continue
            if oferta:
                creadas += 1
    return creadas


def _confirmar_oferta_pendiente(oferta, *, actor=None, correlation=None):
    """Crea la cita de una oferta pendiente. Debe ejecutarse dentro de una transacción."""
    hora = (
        HoraMedica.objects.select_for_update()
        .select_related("bloque__agenda")
        .get(pk=oferta.hora_id)
    )
    if hora.estado != HoraMedica.Estado.OFRECIDA:
        raise ErrorMotor("La hora ya no está reservada para esta oferta.")
    if hora.bloque.agenda.estado != Agenda.Estado.PUBLICADA:
        raise ErrorMotor("La agenda ya no está disponible.")
    if hora.bloque.estado != BloqueAgenda.Estado.DISPONIBLE:
        raise ErrorMotor("El bloque de agenda está bloqueado o suspendido.")

    solapada = Cita.objects.filter(
        solicitud__paciente=oferta.solicitud.paciente,
        estado__in=[Cita.Estado.CONFIRMADA, Cita.Estado.ATENDIDA],
        hora__inicio__lt=hora.fin,
        hora__fin__gt=hora.inicio,
    ).exists()
    if solapada:
        raise ErrorMotor("El paciente ya tiene otra cita en ese horario.")

    cita = Cita.objects.create(
        solicitud=oferta.solicitud,
        hora=hora,
        oferta=oferta,
        estado=Cita.Estado.CONFIRMADA,
        confirmada_en=timezone.now(),
        registrada_por=actor,
        correlation_id=correlation or uuid.uuid4(),
    )
    hora.estado = HoraMedica.Estado.OCUPADA
    hora.version += 1
    hora.save(update_fields=["estado", "version", "actualizado_en"])
    oferta.estado = OfertaHora.Estado.ACEPTADA
    oferta.respondida_en = timezone.now()
    oferta.save(update_fields=["estado", "respondida_en", "actualizado_en"])
    transicionar_solicitud(
        oferta.solicitud,
        Solicitud.Estado.AGENDADA,
        actor=actor,
        motivo="Aceptación de oferta",
        correlation=correlation,
    )
    _mensaje_paciente(
        oferta.solicitud.paciente,
        dedupe_key=f"cita:{cita.uuid}:confirmada",
        asunto="Hora confirmada",
        cuerpo=(
            f"Tu hora de {oferta.solicitud.especialidad.nombre} quedó confirmada para el "
            f"{timezone.localtime(hora.inicio):%d/%m/%Y a las %H:%M}."
        ),
        correlation=cita.correlation_id,
    )
    registrar_auditoria(
        actor=actor,
        accion="OFERTA_ACEPTADA",
        entidad="Cita",
        entidad_id=cita.uuid,
        antes={"oferta": str(oferta.uuid), "estado": "PENDIENTE"},
        despues={"estado": "CONFIRMADA", "hora": hora.pk},
        correlation_id=cita.correlation_id,
    )
    return cita


def aceptar_oferta(oferta_id: int, *, actor=None, correlation=None):
    with _MOTOR_LOCK:
        vencida = False
        cita = None
        evento_vencida = None
        with transaction.atomic():
            try:
                oferta = (
                    OfertaHora.objects.select_related(
                        "solicitud__paciente", "hora__bloque__agenda"
                    )
                    .select_for_update()
                    .get(pk=oferta_id)
                )
            except OfertaHora.DoesNotExist:
                raise ErrorMotor("La oferta no existe.")
            if oferta.estado != OfertaHora.Estado.PENDIENTE:
                if oferta.estado == OfertaHora.Estado.ACEPTADA and hasattr(oferta, "cita"):
                    return oferta.cita
                raise ErrorMotor("La oferta ya no está pendiente.")
            if oferta.expira_en <= timezone.now():
                oferta.estado = OfertaHora.Estado.VENCIDA
                oferta.respondida_en = timezone.now()
                oferta.motivo_cierre = "Vencimiento al momento de aceptar"
                oferta.save(
                    update_fields=["estado", "respondida_en", "motivo_cierre", "actualizado_en"]
                )
                _liberar_hora(oferta.hora, motivo="Oferta vencida")
                _volver_a_lista(oferta.solicitud, "Oferta vencida")
                evento_vencida = crear_evento(
                    tipo="HORA_LIBERADA",
                    entidad_tipo="HoraMedica",
                    entidad_id=oferta.hora_id,
                    idempotency_key=f"vencimiento:{oferta.uuid}",
                    correlation=correlation,
                )
                vencida = True
            else:
                cita = _confirmar_oferta_pendiente(oferta, actor=actor, correlation=correlation)
        if vencida:
            if evento_vencida is not None:
                try:
                    procesar_evento(evento_vencida)
                except ErrorMotor:
                    # El evento queda FALLIDO y con alerta; no se revierte la liberación.
                    pass
            raise ErrorMotor("La oferta venció. La hora será ofrecida a la siguiente persona.")
        return cita


def rechazar_oferta(oferta_id: int, *, actor=None, motivo="Rechazo del paciente", correlation=None):
    with _MOTOR_LOCK, transaction.atomic():
        try:
            oferta = OfertaHora.objects.select_for_update().get(pk=oferta_id)
        except OfertaHora.DoesNotExist:
            raise ErrorMotor("La oferta no existe.")
        if oferta.estado != OfertaHora.Estado.PENDIENTE:
            raise ErrorMotor("La oferta ya no está pendiente.")
        oferta.estado = OfertaHora.Estado.RECHAZADA
        oferta.respondida_en = timezone.now()
        oferta.motivo_cierre = motivo
        oferta.save(update_fields=["estado", "respondida_en", "motivo_cierre", "actualizado_en"])
        _liberar_hora(oferta.hora, motivo="Oferta rechazada")
        _volver_a_lista(oferta.solicitud, "Oferta rechazada")
        registrar_auditoria(
            actor=actor,
            accion="OFERTA_RECHAZADA",
            entidad="OfertaHora",
            entidad_id=oferta.uuid,
            antes={"estado": "PENDIENTE"},
            despues={"estado": "RECHAZADA"},
            motivo=motivo,
            correlation_id=correlation,
        )
        evento = crear_evento(
            tipo="HORA_LIBERADA",
            entidad_tipo="HoraMedica",
            entidad_id=oferta.hora_id,
            idempotency_key=f"rechazo:{oferta.uuid}",
            correlation=correlation,
        )
        try:
            procesar_evento(evento)
        except ErrorMotor:
            # La oferta ya quedó rechazada; el evento fallido conserva alerta.
            pass
    return oferta


def _liberar_hora(hora: HoraMedica, motivo="Liberación"):
    hora = HoraMedica.objects.select_for_update().get(pk=hora.pk)
    if hora.estado in {HoraMedica.Estado.OFRECIDA, HoraMedica.Estado.OCUPADA}:
        if hora.inicio > timezone.now():
            hora.estado = HoraMedica.Estado.DISPONIBLE
            hora.motivo_cancelacion = ""
        else:
            hora.estado = HoraMedica.Estado.CANCELADA
            hora.motivo_cancelacion = motivo
        hora.version += 1
        hora.save(update_fields=["estado", "motivo_cancelacion", "version", "actualizado_en"])


def _volver_a_lista(solicitud: Solicitud, motivo: str):
    if solicitud.estado == Solicitud.Estado.OFERTA_PENDIENTE:
        transicionar_solicitud(
            solicitud,
            Solicitud.Estado.EN_LISTA_ESPERA,
            actor_tipo="SISTEMA",
            motivo=motivo,
        )


def vencer_ofertas(*, ahora_ref=None, limite=100):
    ahora_ref = ahora_ref or timezone.now()
    vencidas = []
    with _MOTOR_LOCK:
        ids = list(
            OfertaHora.objects.filter(
                estado=OfertaHora.Estado.PENDIENTE, expira_en__lte=ahora_ref
            ).values_list("id", flat=True)[:limite]
        )
        for oferta_id in ids:
            with transaction.atomic():
                oferta = OfertaHora.objects.select_for_update().get(pk=oferta_id)
                if oferta.estado != OfertaHora.Estado.PENDIENTE or oferta.expira_en > ahora_ref:
                    continue
                oferta.estado = OfertaHora.Estado.VENCIDA
                oferta.respondida_en = ahora_ref
                oferta.motivo_cierre = "Vencimiento del plazo de respuesta"
                oferta.save(update_fields=["estado", "respondida_en", "motivo_cierre", "actualizado_en"])
                _liberar_hora(oferta.hora, motivo="Oferta vencida")
                _volver_a_lista(oferta.solicitud, "Oferta vencida")
                crear_evento(
                    tipo="HORA_LIBERADA",
                    entidad_tipo="HoraMedica",
                    entidad_id=oferta.hora_id,
                    idempotency_key=f"vencimiento:{oferta.uuid}",
                )
                registrar_auditoria(
                    actor_tipo="SISTEMA",
                    accion="OFERTA_VENCIDA",
                    entidad="OfertaHora",
                    entidad_id=oferta.uuid,
                    antes={"estado": "PENDIENTE"},
                    despues={"estado": "VENCIDA"},
                    correlation_id=oferta.correlation_id,
                )
                vencidas.append(oferta)
    procesar_eventos_pendientes()
    return len(vencidas)


def cancelar_cita(cita_id: int, *, actor=None, motivo="Cancelación", tipo="PACIENTE", correlation=None):
    with _MOTOR_LOCK, transaction.atomic():
        cita = Cita.objects.select_for_update().select_related("hora", "solicitud").get(pk=cita_id)
        if cita.estado not in {Cita.Estado.CONFIRMADA}:
            raise ErrorMotor("Solo se puede cancelar una cita confirmada.")
        cita.estado = (
            Cita.Estado.CANCELADA_PACIENTE if tipo == "PACIENTE" else Cita.Estado.CANCELADA_ESTABLECIMIENTO
        )
        cita.cancelada_en = timezone.now()
        cita.motivo_cancelacion = motivo
        cita.save(update_fields=["estado", "cancelada_en", "motivo_cancelacion", "actualizado_en"])
        _liberar_hora(cita.hora, motivo=motivo)
        if cita.solicitud.estado == Solicitud.Estado.AGENDADA:
            transicionar_solicitud(
                cita.solicitud,
                Solicitud.Estado.EN_LISTA_ESPERA,
                actor=actor,
                actor_tipo="USUARIO" if actor else "SISTEMA",
                motivo=motivo,
                correlation=correlation,
            )
        _mensaje_paciente(
            cita.solicitud.paciente,
            dedupe_key=f"cita:{cita.uuid}:cancelada",
            asunto="Tu hora fue cancelada",
            cuerpo=(
                f"Tu hora de {cita.solicitud.especialidad.nombre} del "
                f"{timezone.localtime(cita.hora.inicio):%d/%m/%Y a las %H:%M} fue cancelada. "
                f"Motivo: {motivo}. Tu solicitud vuelve a la lista de espera."
            ),
            correlation=correlation,
        )
        registrar_auditoria(
            actor=actor,
            accion="CITA_CANCELADA",
            entidad="Cita",
            entidad_id=cita.uuid,
            antes={"estado": "CONFIRMADA"},
            despues={"estado": cita.estado},
            motivo=motivo,
            correlation_id=correlation,
        )
        evento = crear_evento(
            tipo="HORA_LIBERADA",
            entidad_tipo="HoraMedica",
            entidad_id=cita.hora_id,
            idempotency_key=f"cancelacion:{cita.uuid}",
            correlation=correlation,
        )
        try:
            procesar_evento(evento)
        except ErrorMotor:
            # La cita ya quedó cancelada; el evento fallido conserva alerta.
            pass
    return cita


def marcar_atendida(cita_id: int, *, actor=None, correlation=None):
    with _MOTOR_LOCK, transaction.atomic():
        cita = Cita.objects.select_for_update().select_related("solicitud").get(pk=cita_id)
        if cita.estado != Cita.Estado.CONFIRMADA:
            raise ErrorMotor("La cita no está confirmada.")
        cita.estado = Cita.Estado.ATENDIDA
        cita.atendida_en = timezone.now()
        cita.save(update_fields=["estado", "atendida_en", "actualizado_en"])
        transicionar_solicitud(
            cita.solicitud,
            Solicitud.Estado.ATENDIDA,
            actor=actor,
            motivo="Atención registrada",
            correlation=correlation,
        )
        registrar_auditoria(
            actor=actor,
            accion="CITA_ATENDIDA",
            entidad="Cita",
            entidad_id=cita.uuid,
            antes={"estado": "CONFIRMADA"},
            despues={"estado": "ATENDIDA"},
            correlation_id=correlation,
        )
        return cita


def registrar_inasistencia(cita_id: int, *, actor=None, correlation=None):
    with _MOTOR_LOCK, transaction.atomic():
        cita = Cita.objects.select_for_update().select_related("solicitud").get(pk=cita_id)
        if cita.estado != Cita.Estado.CONFIRMADA:
            raise ErrorMotor("La cita no está confirmada.")
        cita.estado = Cita.Estado.NO_ASISTIO
        cita.no_asistio_en = timezone.now()
        cita.save(update_fields=["estado", "no_asistio_en", "actualizado_en"])
        if cita.solicitud.estado == Solicitud.Estado.AGENDADA:
            transicionar_solicitud(
                cita.solicitud,
                Solicitud.Estado.EN_LISTA_ESPERA,
                actor=actor,
                motivo="Inasistencia; sin sanción automática en demo",
                correlation=correlation,
            )
        crear_alerta(
            tipo="DATOS_INCOMPLETOS",
            mensaje=f"Inasistencia registrada para {cita.solicitud.paciente}.",
            entidad="Cita",
            entidad_id=cita.uuid,
            severidad="INFO",
            correlation=correlation,
        )
        registrar_auditoria(
            actor=actor,
            accion="INASISTENCIA",
            entidad="Cita",
            entidad_id=cita.uuid,
            antes={"estado": "CONFIRMADA"},
            despues={"estado": "NO_ASISTIO"},
            correlation_id=correlation,
        )
        return cita


def generar_horas(agenda: Agenda, *, dias_semana: set[int], hora_inicio: time_cls, hora_fin: time_cls, actor=None):
    if agenda.estado == Agenda.Estado.CERRADA:
        raise ErrorMotor("La agenda está cerrada.")
    if agenda.estado == Agenda.Estado.SUSPENDIDA:
        raise ErrorMotor("No se pueden generar horas en una agenda suspendida.")
    if hora_inicio >= hora_fin:
        raise ErrorMotor("La hora de inicio debe ser anterior a la hora de término.")
    if agenda.duracion_min <= 0:
        raise ErrorMotor("La duración debe ser mayor que cero.")
    creadas = 0
    actual = agenda.fecha_inicio
    while actual <= agenda.fecha_fin:
        if actual.weekday() in dias_semana:
            bloque, _ = BloqueAgenda.objects.get_or_create(
                agenda=agenda,
                fecha=actual,
                hora_inicio=hora_inicio,
                defaults={"hora_fin": hora_fin, "estado": BloqueAgenda.Estado.DISPONIBLE},
            )
            if bloque.hora_fin != hora_fin:
                bloque.hora_fin = hora_fin
                bloque.save(update_fields=["hora_fin", "actualizado_en"])
            cursor = timezone.make_aware(datetime.combine(actual, hora_inicio))
            termino = timezone.make_aware(datetime.combine(actual, hora_fin))
            while cursor + timedelta(minutes=agenda.duracion_min) <= termino:
                fin = cursor + timedelta(minutes=agenda.duracion_min)
                solapa = (
                    HoraMedica.objects.filter(
                        bloque__agenda__profesional=agenda.profesional,
                        inicio__lt=fin,
                        fin__gt=cursor,
                    )
                    .exclude(bloque__agenda=agenda)
                    .exists()
                )
                if not solapa:
                    _, creada = HoraMedica.objects.get_or_create(
                        bloque=bloque,
                        inicio=cursor,
                        defaults={"fin": fin, "estado": HoraMedica.Estado.DISPONIBLE},
                    )
                    if creada:
                        creadas += 1
                cursor = fin
        actual += timedelta(days=1)
    registrar_auditoria(
        actor=actor,
        accion="HORAS_GENERADAS",
        entidad="Agenda",
        entidad_id=agenda.pk,
        despues={"horas_creadas": creadas, "desde": str(agenda.fecha_inicio), "hasta": str(agenda.fecha_fin)},
    )
    return creadas


def publicar_agenda(agenda: Agenda, *, actor=None):
    with transaction.atomic():
        if agenda.estado not in {Agenda.Estado.BORRADOR, Agenda.Estado.PUBLICADA}:
            raise ErrorMotor("Solo se puede publicar una agenda en borrador.")
        if not agenda.bloques.exists():
            raise ErrorMotor("Genera al menos un bloque antes de publicar.")
        solapa = Agenda.objects.filter(
            profesional=agenda.profesional,
            estado=Agenda.Estado.PUBLICADA,
            fecha_inicio__lte=agenda.fecha_fin,
            fecha_fin__gte=agenda.fecha_inicio,
        ).exclude(pk=agenda.pk)
        if solapa.exists():
            raise ErrorMotor("Ya existe una agenda publicada del profesional en ese rango de fechas.")
        agenda.estado = Agenda.Estado.PUBLICADA
        agenda.save(update_fields=["estado", "actualizado_en"])
        registrar_auditoria(
            actor=actor,
            accion="AGENDA_PUBLICADA",
            entidad="Agenda",
            entidad_id=agenda.pk,
            despues={"estado": "PUBLICADA"},
        )
    return agenda


def buscar_alternativa(cita: Cita) -> HoraMedica | None:
    agenda_original = cita.hora.bloque.agenda
    return (
        HoraMedica.objects.filter(
            estado=HoraMedica.Estado.DISPONIBLE,
            inicio__gt=timezone.now(),
            bloque__estado=BloqueAgenda.Estado.DISPONIBLE,
            bloque__agenda__estado=Agenda.Estado.PUBLICADA,
            bloque__agenda__especialidad=agenda_original.especialidad,
            bloque__agenda__establecimiento=agenda_original.establecimiento,
        )
        .exclude(bloque__agenda=agenda_original)
        .order_by("inicio")
        .first()
    )


def generar_propuestas_agenda(agenda_id: int, *, motivo="Suspensión de agenda", correlation=None):
    agenda = Agenda.objects.get(pk=agenda_id)
    citas = list(
        Cita.objects.filter(
            hora__bloque__agenda=agenda,
            estado=Cita.Estado.CONFIRMADA,
            hora__inicio__gt=timezone.now(),
        ).select_related("solicitud__paciente", "hora__bloque__agenda")
    )
    creadas = 0
    sin_alternativa = 0
    for cita in citas:
        alternativa = buscar_alternativa(cita)
        cita.estado = Cita.Estado.REAGENDAMIENTO_PENDIENTE
        cita.save(update_fields=["estado", "actualizado_en"])
        if alternativa:
            propuesta, creada = PropuestaReagendamiento.objects.get_or_create(
                cita_original=cita,
                estado=PropuestaReagendamiento.Estado.PENDIENTE,
                defaults={
                    "solicitud": cita.solicitud,
                    "hora_propuesta": alternativa,
                    "motivo": motivo,
                    "correlation_id": correlation or uuid.uuid4(),
                },
            )
            if creada:
                creadas += 1
                _mensaje_paciente(
                    cita.solicitud.paciente,
                    dedupe_key=f"reagendamiento:{propuesta.uuid}:propuesta",
                    asunto="Cambio de agenda: estamos revisando tu hora",
                    cuerpo=(
                        f"Tu hora de {cita.solicitud.especialidad.nombre} del "
                        f"{timezone.localtime(cita.hora.inicio):%d/%m/%Y a las %H:%M} "
                        f"fue afectada por un cambio de agenda. "
                        "Estamos revisando una nueva hora y el equipo confirmará el cambio."
                    ),
                    correlation=correlation,
                )
                crear_alerta(
                    tipo="PROPUESTA_PENDIENTE",
                    mensaje=f"Propuesta de reagendamiento para {cita.solicitud.paciente}.",
                    entidad="PropuestaReagendamiento",
                    entidad_id=propuesta.uuid,
                    severidad="MEDIA",
                    correlation=correlation,
                )
        else:
            sin_alternativa += 1
            crear_alerta(
                tipo="SIN_CANDIDATOS",
                mensaje=f"No hay alternativa para la cita de {cita.solicitud.paciente}.",
                entidad="Cita",
                entidad_id=cita.uuid,
                severidad="ALTA",
                correlation=correlation,
            )
    return {"creadas": creadas, "sin_alternativa": sin_alternativa}


def suspender_agenda(agenda: Agenda, *, actor=None, motivo="Ausencia médica", correlation=None):
    with _MOTOR_LOCK, transaction.atomic():
        agenda = Agenda.objects.select_for_update().get(pk=agenda.pk)
        if agenda.estado not in {Agenda.Estado.PUBLICADA, Agenda.Estado.SUSPENDIDA}:
            raise ErrorMotor("Solo se puede suspender una agenda publicada.")
        agenda.estado = Agenda.Estado.SUSPENDIDA
        agenda.save(update_fields=["estado", "actualizado_en"])
        ofertas_pendientes = OfertaHora.objects.filter(
            hora__bloque__agenda=agenda,
            estado=OfertaHora.Estado.PENDIENTE,
        ).select_related("solicitud")
        for oferta in ofertas_pendientes:
            oferta.estado = OfertaHora.Estado.CANCELADA
            oferta.respondida_en = timezone.now()
            oferta.motivo_cierre = motivo
            oferta.save(update_fields=["estado", "respondida_en", "motivo_cierre", "actualizado_en"])
            _volver_a_lista(oferta.solicitud, "Agenda suspendida")
            _mensaje_paciente(
                oferta.solicitud.paciente,
                dedupe_key=f"oferta:{oferta.uuid}:cancelada",
                asunto="Oferta cancelada por cambio de agenda",
                cuerpo="La oferta fue cancelada porque la agenda médica fue suspendida.",
                correlation=correlation,
            )
        HoraMedica.objects.filter(
            bloque__agenda=agenda,
            inicio__gt=timezone.now(),
            estado__in=[HoraMedica.Estado.DISPONIBLE, HoraMedica.Estado.OFRECIDA],
        ).update(estado=HoraMedica.Estado.CANCELADA, motivo_cancelacion=motivo)
        resultado = generar_propuestas_agenda(agenda.pk, motivo=motivo, correlation=correlation)
        registrar_auditoria(
            actor=actor,
            accion="AGENDA_SUSPENDIDA",
            entidad="Agenda",
            entidad_id=agenda.pk,
            antes={"estado": "PUBLICADA"},
            despues={"estado": "SUSPENDIDA", **resultado},
            motivo=motivo,
            correlation_id=correlation,
        )
        return resultado


def _crear_cita_reagendada(propuesta, hora, *, actor=None, motivo="Aprobación humana", correlation=None):
    solapada = Cita.objects.filter(
        solicitud__paciente=propuesta.solicitud.paciente,
        estado__in=[Cita.Estado.CONFIRMADA, Cita.Estado.ATENDIDA],
        hora__inicio__lt=hora.fin,
        hora__fin__gt=hora.inicio,
    ).exclude(pk=propuesta.cita_original_id).exists()
    if solapada:
        raise ErrorMotor("El paciente ya tiene otra cita en ese horario.")
    nueva = Cita.objects.create(
        solicitud=propuesta.solicitud,
        hora=hora,
        estado=Cita.Estado.CONFIRMADA,
        confirmada_en=timezone.now(),
        registrada_por=actor,
        correlation_id=correlation or uuid.uuid4(),
    )
    hora.estado = HoraMedica.Estado.OCUPADA
    hora.version += 1
    hora.save(update_fields=["estado", "version", "actualizado_en"])
    original = propuesta.cita_original
    original.estado = Cita.Estado.REAGENDADA
    original.save(update_fields=["estado", "actualizado_en"])
    propuesta.estado = PropuestaReagendamiento.Estado.APROBADA
    propuesta.revisada_por = actor
    propuesta.revisada_en = timezone.now()
    propuesta.decision_motivo = motivo
    propuesta.save(
        update_fields=["estado", "revisada_por", "revisada_en", "decision_motivo", "actualizado_en"]
    )
    _mensaje_paciente(
        propuesta.solicitud.paciente,
        dedupe_key=f"reagendamiento:{propuesta.uuid}:aprobado",
        asunto="Tu hora fue reagendada",
        cuerpo=(
            f"Tu atención de {propuesta.solicitud.especialidad.nombre} fue reagendada para el "
            f"{timezone.localtime(hora.inicio):%d/%m/%Y a las %H:%M}."
        ),
        correlation=propuesta.correlation_id,
    )
    registrar_auditoria(
        actor=actor,
        accion="PROPUESTA_APROBADA",
        entidad="PropuestaReagendamiento",
        entidad_id=propuesta.uuid,
        antes={"estado": "PENDIENTE_REVISION"},
        despues={"estado": "APROBADA", "cita_nueva": str(nueva.uuid)},
        motivo=motivo,
        correlation_id=correlation,
    )
    return nueva


def aprobar_propuesta(propuesta_id: int, *, actor=None, motivo="Aprobación humana", correlation=None):
    fallo = None
    nueva = None
    with _MOTOR_LOCK:
        with transaction.atomic():
            propuesta = (
                PropuestaReagendamiento.objects.select_for_update()
                .select_related("cita_original", "solicitud", "hora_propuesta__bloque__agenda")
                .get(pk=propuesta_id)
            )
            if propuesta.estado != PropuestaReagendamiento.Estado.PENDIENTE:
                raise ErrorMotor("La propuesta ya no está pendiente.")
            hora = HoraMedica.objects.select_for_update().select_related("bloque__agenda").get(
                pk=propuesta.hora_propuesta_id
            )
            if not hora.disponible:
                propuesta.estado = PropuestaReagendamiento.Estado.FALLIDA
                propuesta.revisada_por = actor
                propuesta.revisada_en = timezone.now()
                propuesta.decision_motivo = "La hora propuesta ya no está disponible."
                propuesta.save(
                    update_fields=[
                        "estado",
                        "revisada_por",
                        "revisada_en",
                        "decision_motivo",
                        "actualizado_en",
                    ]
                )
                crear_alerta(
                    tipo="PROPUESTA_FALLIDA",
                    mensaje=f"La propuesta para {propuesta.solicitud.paciente} ya no es viable.",
                    entidad="PropuestaReagendamiento",
                    entidad_id=propuesta.uuid,
                    severidad="ALTA",
                    correlation=correlation,
                )
                fallo = ErrorMotor(
                    "La hora propuesta ya no está disponible. La propuesta quedó fallida."
                )
            else:
                nueva = _crear_cita_reagendada(
                    propuesta, hora, actor=actor, motivo=motivo, correlation=correlation
                )
    if fallo is not None:
        raise fallo
    return nueva


def rechazar_propuesta(propuesta_id: int, *, actor=None, motivo="Rechazo humano", correlation=None):
    with _MOTOR_LOCK, transaction.atomic():
        propuesta = PropuestaReagendamiento.objects.select_for_update().select_related(
            "cita_original", "solicitud"
        ).get(pk=propuesta_id)
        if propuesta.estado != PropuestaReagendamiento.Estado.PENDIENTE:
            raise ErrorMotor("La propuesta ya no está pendiente.")
        propuesta.estado = PropuestaReagendamiento.Estado.RECHAZADA
        propuesta.revisada_por = actor
        propuesta.revisada_en = timezone.now()
        propuesta.decision_motivo = motivo
        propuesta.save(update_fields=["estado", "revisada_por", "revisada_en", "decision_motivo", "actualizado_en"])
        original = propuesta.cita_original
        original.estado = Cita.Estado.CANCELADA_ESTABLECIMIENTO
        original.cancelada_en = timezone.now()
        original.motivo_cancelacion = motivo
        original.save(update_fields=["estado", "cancelada_en", "motivo_cancelacion", "actualizado_en"])
        if propuesta.solicitud.estado == Solicitud.Estado.AGENDADA:
            transicionar_solicitud(
                propuesta.solicitud,
                Solicitud.Estado.EN_LISTA_ESPERA,
                actor=actor,
                motivo="Propuesta de reagendamiento rechazada",
                correlation=correlation,
            )
        _mensaje_paciente(
            propuesta.solicitud.paciente,
            dedupe_key=f"reagendamiento:{propuesta.uuid}:rechazado",
            asunto="Tu hora fue cancelada",
            cuerpo=(
                f"La propuesta de reagendamiento para tu atención de "
                f"{propuesta.solicitud.especialidad.nombre} no fue aprobada. "
                f"Tu hora del {timezone.localtime(original.hora.inicio):%d/%m/%Y a las %H:%M} "
                f"fue cancelada. Motivo: {motivo}. Tu solicitud vuelve a la lista de espera."
            ),
            correlation=correlation,
        )
        registrar_auditoria(
            actor=actor,
            accion="PROPUESTA_RECHAZADA",
            entidad="PropuestaReagendamiento",
            entidad_id=propuesta.uuid,
            antes={"estado": "PENDIENTE_REVISION"},
            despues={"estado": "RECHAZADA"},
            motivo=motivo,
            correlation_id=correlation,
        )
        return propuesta


def crear_cita_manual(
    solicitud: Solicitud,
    hora: HoraMedica,
    *,
    actor=None,
    correlation=None,
    motivo="Reserva manual autorizada",
    accion="CITA_MANUAL",
    notificar=False,
):
    with _MOTOR_LOCK, transaction.atomic():
        hora = (
            HoraMedica.objects.select_for_update()
            .select_related("bloque__agenda__especialidad")
            .get(pk=hora.pk)
        )
        if not hora.disponible:
            raise ErrorMotor("La hora ya no está disponible.")
        if hora.bloque.agenda.especialidad_id != solicitud.especialidad_id:
            raise ErrorMotor("La hora seleccionada no corresponde a la especialidad solicitada.")
        if solicitud.estado != Solicitud.Estado.EN_LISTA_ESPERA:
            raise ErrorMotor("La solicitud no está en lista de espera.")
        if Cita.objects.filter(
            solicitud=solicitud, estado__in=[Cita.Estado.CONFIRMADA, Cita.Estado.ATENDIDA]
        ).exists():
            raise ErrorMotor("La solicitud ya tiene una cita activa.")
        solapada = Cita.objects.filter(
            solicitud__paciente=solicitud.paciente,
            estado__in=[Cita.Estado.CONFIRMADA, Cita.Estado.ATENDIDA],
            hora__inicio__lt=hora.fin,
            hora__fin__gt=hora.inicio,
        ).exists()
        if solapada:
            raise ErrorMotor("El paciente ya tiene otra cita en ese horario.")
        try:
            with transaction.atomic():
                cita = Cita.objects.create(
                    solicitud=solicitud,
                    hora=hora,
                    estado=Cita.Estado.CONFIRMADA,
                    confirmada_en=timezone.now(),
                    registrada_por=actor,
                    correlation_id=correlation or uuid.uuid4(),
                )
        except IntegrityError:
            raise ErrorMotor(
                "La hora acaba de ser reservada por otra persona. Elige otra hora disponible."
            )
        hora.estado = HoraMedica.Estado.OCUPADA
        hora.version += 1
        hora.save(update_fields=["estado", "version", "actualizado_en"])
        transicionar_solicitud(
            solicitud,
            Solicitud.Estado.AGENDADA,
            actor=actor,
            motivo=motivo,
            correlation=correlation,
        )
        if notificar:
            _mensaje_paciente(
                solicitud.paciente,
                dedupe_key=f"cita:{cita.uuid}:confirmada",
                asunto="Hora confirmada",
                cuerpo=(
                    f"Tu hora de {solicitud.especialidad.nombre} quedó confirmada para el "
                    f"{timezone.localtime(hora.inicio):%d/%m/%Y a las %H:%M}."
                ),
                correlation=cita.correlation_id,
            )
        registrar_auditoria(
            actor=actor,
            accion=accion,
            entidad="Cita",
            entidad_id=cita.uuid,
            despues={"hora": hora.pk, "solicitud": str(solicitud.uuid)},
            correlation_id=cita.correlation_id,
        )
        return cita


def crear_oferta_manual(solicitud: Solicitud, hora: HoraMedica, *, actor=None, correlation=None):
    with _MOTOR_LOCK, transaction.atomic():
        hora = HoraMedica.objects.select_for_update().get(pk=hora.pk)
        if not hora.disponible:
            raise ErrorMotor("La hora ya no está disponible.")
        if solicitud.estado != Solicitud.Estado.EN_LISTA_ESPERA:
            raise ErrorMotor("La solicitud no está en lista de espera.")
        if Cita.objects.filter(
            solicitud=solicitud, estado__in=[Cita.Estado.CONFIRMADA, Cita.Estado.ATENDIDA]
        ).exists():
            raise ErrorMotor("La solicitud ya tiene una cita activa.")
        if OfertaHora.objects.filter(solicitud=solicitud, estado=OfertaHora.Estado.PENDIENTE).exists():
            raise ErrorMotor("La solicitud ya tiene una oferta pendiente.")
        horas_vigencia = Parametro.get_int("oferta.vigencia_horas", 48)
        oferta = OfertaHora.objects.create(
            solicitud=solicitud,
            hora=hora,
            estado=OfertaHora.Estado.PENDIENTE,
            canal=solicitud.paciente.canal_preferido,
            expira_en=timezone.now() + timedelta(hours=horas_vigencia),
            intento=OfertaHora.objects.filter(solicitud=solicitud, hora=hora).count() + 1,
            idempotency_key=f"manual:{hora.pk}:{solicitud.pk}:{uuid.uuid4().hex[:8]}",
            creada_por_sistema=False,
            creada_por=actor,
            correlation_id=correlation or uuid.uuid4(),
        )
        hora.estado = HoraMedica.Estado.OFRECIDA
        hora.version += 1
        hora.save(update_fields=["estado", "version", "actualizado_en"])
        transicionar_solicitud(
            solicitud,
            Solicitud.Estado.OFERTA_PENDIENTE,
            actor=actor,
            motivo="Oferta manual autorizada",
            correlation=correlation,
        )
        _mensaje_paciente(
            solicitud.paciente,
            dedupe_key=f"oferta:{oferta.uuid}:creada",
            asunto="Tienes una nueva oferta de hora",
            cuerpo=(
                f"Hay una hora de {solicitud.especialidad.nombre} el "
                f"{timezone.localtime(hora.inicio):%d/%m/%Y a las %H:%M}."
            ),
            correlation=oferta.correlation_id,
        )
        registrar_auditoria(
            actor=actor,
            accion="OFERTA_MANUAL",
            entidad="OfertaHora",
            entidad_id=oferta.uuid,
            despues={"hora": hora.pk, "solicitud": str(solicitud.uuid)},
            correlation_id=oferta.correlation_id,
        )
        return oferta
