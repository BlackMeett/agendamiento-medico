from __future__ import annotations

import uuid
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

UUID_DEFAULT = uuid.uuid4


class MarcasTiempo(models.Model):
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Establecimiento(MarcasTiempo):
    codigo = models.CharField(max_length=30, unique=True)
    nombre = models.CharField(max_length=150)
    tipo = models.CharField(max_length=40, default="CESFAM")
    comuna = models.CharField(max_length=80, blank=True)
    region = models.CharField(max_length=80, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "establecimiento"
        verbose_name_plural = "establecimientos"

    def __str__(self):
        return f"{self.nombre} ({self.codigo})"


class Especialidad(MarcasTiempo):
    codigo = models.CharField(max_length=30, unique=True)
    nombre = models.CharField(max_length=120)
    activa = models.BooleanField(default=True)
    requiere_derivacion = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "especialidad"
        verbose_name_plural = "especialidades"

    def __str__(self):
        return self.nombre


class Profesional(MarcasTiempo):
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    documento = models.CharField(max_length=30, unique=True)
    especialidad = models.ForeignKey(Especialidad, on_delete=models.PROTECT, related_name="profesionales")
    establecimiento = models.ForeignKey(Establecimiento, on_delete=models.PROTECT, related_name="profesionales")
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["apellidos", "nombres"]
        verbose_name = "profesional"
        verbose_name_plural = "profesionales"

    def __str__(self):
        return f"{self.apellidos}, {self.nombres} · {self.especialidad}"


class Paciente(MarcasTiempo):
    class TipoDocumento(models.TextChoices):
        RUT = "RUT", "RUT sintético"
        PASAPORTE = "PASAPORTE", "Pasaporte"
        OTRO = "OTRO", "Otro"

    class EstadoContacto(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente de contacto"
        CONTACTADO = "CONTACTADO", "Contactado"
        NO_CONTACTABLE = "NO_CONTACTABLE", "No contactable"
        CONFIRMADO = "CONFIRMADO", "Contacto confirmado"

    class CanalPreferido(models.TextChoices):
        PORTAL = "PORTAL", "Portal del paciente"
        EMAIL = "EMAIL", "Correo electrónico"
        SMS = "SMS", "SMS"
        WHATSAPP = "WHATSAPP", "WhatsApp"

    uuid = models.UUIDField(default=UUID_DEFAULT, unique=True, editable=False)
    tipo_documento = models.CharField(max_length=20, choices=TipoDocumento.choices, default=TipoDocumento.RUT)
    numero_documento = models.CharField(max_length=30)
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    fecha_nacimiento = models.DateField()
    telefono = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    canal_preferido = models.CharField(
        max_length=20, choices=CanalPreferido.choices, default=CanalPreferido.PORTAL
    )
    consentimiento_notificaciones = models.BooleanField(default=True)
    establecimiento_referencia = models.ForeignKey(
        Establecimiento, on_delete=models.PROTECT, related_name="pacientes"
    )
    estado_contacto = models.CharField(
        max_length=20, choices=EstadoContacto.choices, default=EstadoContacto.PENDIENTE
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="paciente",
        help_text="Cuenta del portal, si fue activada.",
    )
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["apellidos", "nombres"]
        verbose_name = "paciente"
        verbose_name_plural = "pacientes"
        constraints = [
            models.UniqueConstraint(
                fields=["tipo_documento", "numero_documento"],
                name="uq_paciente_documento",
            )
        ]
        indexes = [models.Index(fields=["apellidos", "nombres"])]

    def __str__(self):
        return f"{self.apellidos}, {self.nombres}"

    @property
    def nombre_completo(self):
        return f"{self.nombres} {self.apellidos}"

    @property
    def documento_enmascarado(self):
        valor = self.numero_documento
        if len(valor) <= 4:
            return "••••"
        return f"••••{valor[-3:]}"

    @property
    def edad(self):
        hoy = timezone.localdate()
        return hoy.year - self.fecha_nacimiento.year - (
            (hoy.month, hoy.day) < (self.fecha_nacimiento.month, self.fecha_nacimiento.day)
        )

    @property
    def tiene_cuenta(self):
        return self.user_id is not None


class PreferenciaDisponibilidad(MarcasTiempo):
    class Dia(models.IntegerChoices):
        LUNES = 0, "Lunes"
        MARTES = 1, "Martes"
        MIERCOLES = 2, "Miércoles"
        JUEVES = 3, "Jueves"
        VIERNES = 4, "Viernes"
        SABADO = 5, "Sábado"
        DOMINGO = 6, "Domingo"

    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name="preferencias")
    dia_semana = models.PositiveSmallIntegerField(choices=Dia.choices)
    hora_desde = models.TimeField()
    hora_hasta = models.TimeField()
    es_restriccion = models.BooleanField(
        default=True,
        help_text="Si está activo, el motor no ofrecerá horas fuera de esta ventana.",
    )
    vigente = models.BooleanField(default=True)

    class Meta:
        ordering = ["paciente", "dia_semana", "hora_desde"]
        verbose_name = "preferencia de disponibilidad"
        verbose_name_plural = "preferencias de disponibilidad"
        constraints = [
            models.CheckConstraint(
                condition=Q(hora_desde__lt=models.F("hora_hasta")),
                name="ck_preferencia_rango",
            )
        ]

    def __str__(self):
        return f"{self.get_dia_semana_display()} {self.hora_desde:%H:%M}–{self.hora_hasta:%H:%M}"

    def clean(self):
        if self.hora_desde and self.hora_hasta and self.hora_desde >= self.hora_hasta:
            raise ValidationError("La hora de inicio debe ser anterior a la hora de término.")


class Solicitud(MarcasTiempo):
    class Estado(models.TextChoices):
        INGRESADA = "INGRESADA", "Ingresada"
        PENDIENTE_REVISION = "PENDIENTE_REVISION", "Pendiente de revisión"
        VALIDADA = "VALIDADA", "Validada"
        EN_LISTA_ESPERA = "EN_LISTA_ESPERA", "En lista de espera"
        OFERTA_PENDIENTE = "OFERTA_PENDIENTE", "Con oferta pendiente"
        AGENDADA = "AGENDADA", "Agendada"
        ATENDIDA = "ATENDIDA", "Atendida"
        RECHAZADA = "RECHAZADA", "Rechazada"
        CANCELADA = "CANCELADA", "Cancelada"
        CERRADA = "CERRADA", "Cerrada"

    class Origen(models.TextChoices):
        APS = "APS", "Derivación desde atención primaria"
        INTERNA = "INTERNA", "Derivación interna"
        EXTERNA = "EXTERNA", "Derivación externa"
        CONTROL = "CONTROL", "Control pendiente"
        MANUAL = "MANUAL", "Ingreso manual autorizado"
        PORTAL = "PORTAL", "Solicitud desde el portal del paciente"

    uuid = models.UUIDField(default=UUID_DEFAULT, unique=True, editable=False)
    paciente = models.ForeignKey(Paciente, on_delete=models.PROTECT, related_name="solicitudes")
    especialidad = models.ForeignKey(Especialidad, on_delete=models.PROTECT, related_name="solicitudes")
    establecimiento_origen = models.ForeignKey(
        Establecimiento, on_delete=models.PROTECT, related_name="solicitudes_origen"
    )
    establecimiento_destino = models.ForeignKey(
        Establecimiento,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="solicitudes_destino",
    )
    origen = models.CharField(max_length=20, choices=Origen.choices, default=Origen.APS)
    estado = models.CharField(max_length=30, choices=Estado.choices, default=Estado.INGRESADA)
    fecha_ingreso = models.DateField(default=timezone.localdate)
    fecha_validacion = models.DateField(null=True, blank=True)
    fecha_lista_espera = models.DateField(null=True, blank=True)
    referencia_externa = models.CharField(max_length=80, blank=True)
    observaciones = models.TextField(blank=True)
    motivo_cierre = models.TextField(blank=True)
    creada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="solicitudes_creadas",
    )

    class Meta:
        ordering = ["fecha_ingreso", "creado_en", "id"]
        verbose_name = "solicitud de atención"
        verbose_name_plural = "solicitudes de atención"
        constraints = [
            models.UniqueConstraint(
                fields=["referencia_externa"],
                condition=~Q(referencia_externa=""),
                name="uq_solicitud_referencia_externa",
            )
        ]
        indexes = [
            models.Index(fields=["estado", "especialidad", "fecha_ingreso"]),
            models.Index(fields=["paciente", "estado"]),
        ]

    def __str__(self):
        return f"{self.short} · {self.paciente} · {self.especialidad}"

    @property
    def short(self):
        return str(self.uuid)[:8]

    @property
    def dias_espera(self):
        base = self.fecha_lista_espera or self.fecha_ingreso
        return max((timezone.localdate() - base).days, 0)

    @property
    def activa(self):
        return self.estado in {
            self.Estado.EN_LISTA_ESPERA,
            self.Estado.OFERTA_PENDIENTE,
            self.Estado.AGENDADA,
        }

    @property
    def en_lista(self):
        return self.estado in {self.Estado.EN_LISTA_ESPERA, self.Estado.OFERTA_PENDIENTE}

    @property
    def cita_activa(self):
        return self.citas.filter(estado__in=[Cita.Estado.CONFIRMADA, Cita.Estado.ATENDIDA]).first()


class DatosClinicosSolicitud(MarcasTiempo):
    solicitud = models.OneToOneField(
        Solicitud, on_delete=models.CASCADE, related_name="datos_clinicos"
    )
    motivo_derivacion = models.TextField(blank=True)
    diagnostico = models.CharField(max_length=180, blank=True)
    notas = models.TextField(blank=True)
    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="datos_clinicos_actualizados",
    )

    class Meta:
        verbose_name = "datos clínicos de solicitud"
        verbose_name_plural = "datos clínicos de solicitudes"

    def __str__(self):
        return f"Datos clínicos de {self.solicitud_id}"


class HistorialEstadoSolicitud(models.Model):
    solicitud = models.ForeignKey(Solicitud, on_delete=models.CASCADE, related_name="historial")
    estado_anterior = models.CharField(max_length=30, blank=True)
    estado_nuevo = models.CharField(max_length=30)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="transiciones_solicitud",
    )
    actor_tipo = models.CharField(max_length=20, default="USUARIO")
    motivo = models.TextField(blank=True)
    correlation_id = models.UUIDField(default=UUID_DEFAULT, db_index=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha"]
        verbose_name = "historial de estado"
        verbose_name_plural = "historial de estados"

    def __str__(self):
        return f"{self.estado_anterior or '—'} → {self.estado_nuevo}"


class Agenda(MarcasTiempo):
    class Estado(models.TextChoices):
        BORRADOR = "BORRADOR", "Borrador"
        PUBLICADA = "PUBLICADA", "Publicada"
        SUSPENDIDA = "SUSPENDIDA", "Suspendida"
        CERRADA = "CERRADA", "Cerrada"

    uuid = models.UUIDField(default=UUID_DEFAULT, unique=True, editable=False)
    profesional = models.ForeignKey(Profesional, on_delete=models.PROTECT, related_name="agendas")
    establecimiento = models.ForeignKey(Establecimiento, on_delete=models.PROTECT, related_name="agendas")
    especialidad = models.ForeignKey(Especialidad, on_delete=models.PROTECT, related_name="agendas")
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    duracion_min = models.PositiveSmallIntegerField(default=30)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.BORRADOR)
    creada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="agendas_creadas",
    )

    class Meta:
        ordering = ["-fecha_inicio", "profesional"]
        verbose_name = "agenda"
        verbose_name_plural = "agendas"
        constraints = [
            models.CheckConstraint(
                condition=Q(fecha_inicio__lte=models.F("fecha_fin")),
                name="ck_agenda_fechas",
            )
        ]

    def __str__(self):
        return f"{self.profesional} · {self.fecha_inicio:%d/%m/%Y}–{self.fecha_fin:%d/%m/%Y}"


class BloqueAgenda(MarcasTiempo):
    class Estado(models.TextChoices):
        DISPONIBLE = "DISPONIBLE", "Disponible"
        BLOQUEADO = "BLOQUEADO", "Bloqueado"
        SUSPENDIDO = "SUSPENDIDO", "Suspendido"

    agenda = models.ForeignKey(Agenda, on_delete=models.CASCADE, related_name="bloques")
    fecha = models.DateField()
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.DISPONIBLE)
    motivo = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["agenda", "fecha", "hora_inicio"]
        verbose_name = "bloque de agenda"
        verbose_name_plural = "bloques de agenda"
        constraints = [
            models.UniqueConstraint(
                fields=["agenda", "fecha", "hora_inicio"],
                name="uq_bloque_agenda_inicio",
            ),
            models.CheckConstraint(
                condition=Q(hora_inicio__lt=models.F("hora_fin")),
                name="ck_bloque_rango",
            ),
        ]

    def __str__(self):
        return f"{self.fecha:%d/%m/%Y} {self.hora_inicio:%H:%M}–{self.hora_fin:%H:%M}"


class HoraMedica(MarcasTiempo):
    class Estado(models.TextChoices):
        DISPONIBLE = "DISPONIBLE", "Disponible"
        OFRECIDA = "OFRECIDA", "Ofrecida"
        OCUPADA = "OCUPADA", "Ocupada"
        BLOQUEADA = "BLOQUEADA", "Bloqueada"
        CANCELADA = "CANCELADA", "Cancelada"

    uuid = models.UUIDField(default=UUID_DEFAULT, unique=True, editable=False)
    bloque = models.ForeignKey(BloqueAgenda, on_delete=models.PROTECT, related_name="horas")
    inicio = models.DateTimeField()
    fin = models.DateTimeField()
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.DISPONIBLE)
    version = models.PositiveIntegerField(default=1)
    motivo_cancelacion = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["inicio"]
        verbose_name = "hora médica"
        verbose_name_plural = "horas médicas"
        constraints = [
            models.UniqueConstraint(fields=["bloque", "inicio"], name="uq_hora_bloque_inicio"),
            models.CheckConstraint(condition=Q(inicio__lt=models.F("fin")), name="ck_hora_rango"),
        ]
        indexes = [models.Index(fields=["inicio", "estado"])]

    def __str__(self):
        return f"{self.inicio:%d/%m/%Y %H:%M} · {self.get_estado_display()}"

    @property
    def agenda(self):
        return self.bloque.agenda

    @property
    def disponible(self):
        return (
            self.estado == self.Estado.DISPONIBLE
            and self.inicio > timezone.now()
            and self.bloque.estado == BloqueAgenda.Estado.DISPONIBLE
            and self.bloque.agenda.estado == Agenda.Estado.PUBLICADA
        )


class OfertaHora(MarcasTiempo):
    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        ACEPTADA = "ACEPTADA", "Aceptada"
        RECHAZADA = "RECHAZADA", "Rechazada"
        VENCIDA = "VENCIDA", "Vencida"
        CANCELADA = "CANCELADA", "Cancelada"

    uuid = models.UUIDField(default=UUID_DEFAULT, unique=True, editable=False)
    solicitud = models.ForeignKey(Solicitud, on_delete=models.PROTECT, related_name="ofertas")
    hora = models.ForeignKey(HoraMedica, on_delete=models.PROTECT, related_name="ofertas")
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDIENTE)
    canal = models.CharField(max_length=20, default="PORTAL")
    expira_en = models.DateTimeField()
    respondida_en = models.DateTimeField(null=True, blank=True)
    intento = models.PositiveSmallIntegerField(default=1)
    idempotency_key = models.CharField(max_length=180, unique=True)
    creada_por_sistema = models.BooleanField(default=True)
    creada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ofertas_creadas",
    )
    motivo_cierre = models.CharField(max_length=255, blank=True)
    correlation_id = models.UUIDField(default=UUID_DEFAULT, db_index=True)

    class Meta:
        ordering = ["-creado_en"]
        verbose_name = "oferta de hora"
        verbose_name_plural = "ofertas de hora"
        constraints = [
            models.UniqueConstraint(
                fields=["hora"],
                condition=Q(estado="PENDIENTE"),
                name="uq_oferta_pendiente_hora",
            ),
            models.UniqueConstraint(
                fields=["solicitud"],
                condition=Q(estado="PENDIENTE"),
                name="uq_oferta_pendiente_solicitud",
            ),
        ]
        indexes = [models.Index(fields=["estado", "expira_en"])]

    def __str__(self):
        return f"Oferta {self.short} · {self.solicitud}"

    @property
    def short(self):
        return str(self.uuid)[:8]

    @property
    def vigente(self):
        return self.estado == self.Estado.PENDIENTE and self.expira_en > timezone.now()


class Cita(MarcasTiempo):
    class Estado(models.TextChoices):
        CONFIRMADA = "CONFIRMADA", "Confirmada"
        ATENDIDA = "ATENDIDA", "Atendida"
        NO_ASISTIO = "NO_ASISTIO", "No asistió"
        CANCELADA_PACIENTE = "CANCELADA_PACIENTE", "Cancelada por paciente"
        CANCELADA_ESTABLECIMIENTO = "CANCELADA_ESTABLECIMIENTO", "Cancelada por establecimiento"
        REAGENDAMIENTO_PENDIENTE = "REAGENDAMIENTO_PENDIENTE", "Reagendamiento pendiente"
        REAGENDADA = "REAGENDADA", "Reagendada"

    uuid = models.UUIDField(default=UUID_DEFAULT, unique=True, editable=False)
    solicitud = models.ForeignKey(Solicitud, on_delete=models.PROTECT, related_name="citas")
    hora = models.ForeignKey(HoraMedica, on_delete=models.PROTECT, related_name="citas")
    oferta = models.OneToOneField(
        OfertaHora,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cita",
    )
    estado = models.CharField(max_length=30, choices=Estado.choices, default=Estado.CONFIRMADA)
    confirmada_en = models.DateTimeField(default=timezone.now)
    atendida_en = models.DateTimeField(null=True, blank=True)
    cancelada_en = models.DateTimeField(null=True, blank=True)
    no_asistio_en = models.DateTimeField(null=True, blank=True)
    motivo_cancelacion = models.CharField(max_length=255, blank=True)
    registrada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="citas_registradas",
    )
    correlation_id = models.UUIDField(default=UUID_DEFAULT, db_index=True)

    class Meta:
        ordering = ["-hora__inicio"]
        verbose_name = "cita"
        verbose_name_plural = "citas"
        constraints = [
            models.UniqueConstraint(
                fields=["hora"],
                condition=Q(estado__in=["CONFIRMADA", "ATENDIDA"]),
                name="uq_cita_activa_hora",
            ),
            models.UniqueConstraint(
                fields=["solicitud"],
                condition=Q(estado__in=["CONFIRMADA", "ATENDIDA"]),
                name="uq_cita_activa_solicitud",
            ),
        ]

    def __str__(self):
        return f"Cita {self.short} · {self.solicitud.paciente} · {self.hora.inicio:%d/%m/%Y %H:%M}"

    @property
    def short(self):
        return str(self.uuid)[:8]

    @property
    def activa(self):
        return self.estado in {self.Estado.CONFIRMADA, self.Estado.ATENDIDA}


class PropuestaReagendamiento(MarcasTiempo):
    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE_REVISION", "Pendiente de revisión"
        APROBADA = "APROBADA", "Aprobada"
        RECHAZADA = "RECHAZADA", "Rechazada"
        FALLIDA = "FALLIDA", "Fallida"
        CANCELADA = "CANCELADA", "Cancelada"

    uuid = models.UUIDField(default=UUID_DEFAULT, unique=True, editable=False)
    cita_original = models.ForeignKey(Cita, on_delete=models.PROTECT, related_name="propuestas")
    solicitud = models.ForeignKey(Solicitud, on_delete=models.PROTECT, related_name="propuestas")
    hora_propuesta = models.ForeignKey(HoraMedica, on_delete=models.PROTECT, related_name="propuestas")
    estado = models.CharField(max_length=30, choices=Estado.choices, default=Estado.PENDIENTE)
    motivo = models.CharField(max_length=255)
    creada_por_sistema = models.BooleanField(default=True)
    revisada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="propuestas_revisadas",
    )
    revisada_en = models.DateTimeField(null=True, blank=True)
    decision_motivo = models.TextField(blank=True)
    correlation_id = models.UUIDField(default=UUID_DEFAULT, db_index=True)

    class Meta:
        ordering = ["-creado_en"]
        verbose_name = "propuesta de reagendamiento"
        verbose_name_plural = "propuestas de reagendamiento"
        constraints = [
            models.UniqueConstraint(
                fields=["cita_original"],
                condition=Q(estado="PENDIENTE_REVISION"),
                name="uq_propuesta_pendiente_cita",
            )
        ]

    def __str__(self):
        return f"Propuesta {self.short} · {self.solicitud.paciente}"

    @property
    def short(self):
        return str(self.uuid)[:8]


class EventoMotor(MarcasTiempo):
    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        PROCESANDO = "PROCESANDO", "Procesando"
        COMPLETADO = "COMPLETADO", "Completado"
        FALLIDO = "FALLIDO", "Fallido"
        DESCARTADO = "DESCARTADO", "Descartado"

    idempotency_key = models.CharField(max_length=180, unique=True)
    tipo = models.CharField(max_length=40)
    entidad_tipo = models.CharField(max_length=40)
    entidad_id = models.CharField(max_length=80)
    payload = models.JSONField(default=dict, blank=True)
    correlation_id = models.UUIDField(default=UUID_DEFAULT, db_index=True)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDIENTE)
    intentos = models.PositiveSmallIntegerField(default=0)
    error = models.CharField(max_length=255, blank=True)
    procesado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["estado", "creado_en"]
        verbose_name = "evento del motor"
        verbose_name_plural = "eventos del motor"
        indexes = [models.Index(fields=["estado", "creado_en"])]

    def __str__(self):
        return f"{self.tipo} · {self.estado} · {self.idempotency_key}"
