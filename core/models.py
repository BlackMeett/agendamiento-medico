from __future__ import annotations

import json
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

UUID_DEFAULT = uuid.uuid4


def nuevo_correlation_id() -> str:
    return str(uuid.uuid4())


class Parametro(models.Model):
    clave = models.CharField(max_length=120, unique=True)
    valor = models.CharField(max_length=255)
    descripcion = models.CharField(max_length=255, blank=True)
    grupo = models.CharField(max_length=60, default="general")
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["grupo", "clave"]
        verbose_name = "parámetro"
        verbose_name_plural = "parámetros"

    def __str__(self):
        return f"{self.clave}={self.valor}"

    @classmethod
    def get(cls, clave: str, default: str = "") -> str:
        obj = cls.objects.filter(clave=clave).first()
        return obj.valor if obj else default

    @classmethod
    def get_int(cls, clave: str, default: int) -> int:
        try:
            return int(cls.get(clave, str(default)))
        except (TypeError, ValueError):
            return default


class EventoAuditoria(models.Model):
    class ActorTipo(models.TextChoices):
        USUARIO = "USUARIO", "Usuario"
        SISTEMA = "SISTEMA", "Sistema"
        PACIENTE = "PACIENTE", "Paciente"

    fecha = models.DateTimeField(auto_now_add=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="eventos_auditoria",
    )
    actor_tipo = models.CharField(max_length=20, choices=ActorTipo.choices, default=ActorTipo.USUARIO)
    accion = models.CharField(max_length=80)
    entidad = models.CharField(max_length=60)
    entidad_id = models.CharField(max_length=80, blank=True)
    estado_anterior = models.JSONField(null=True, blank=True)
    estado_nuevo = models.JSONField(null=True, blank=True)
    motivo = models.TextField(blank=True)
    resultado = models.CharField(max_length=20, default="OK")
    correlation_id = models.UUIDField(default=UUID_DEFAULT, db_index=True)
    ip_hash = models.CharField(max_length=64, blank=True)
    user_agent_resumido = models.CharField(max_length=180, blank=True)

    class Meta:
        ordering = ["-fecha"]
        verbose_name = "evento de auditoría"
        verbose_name_plural = "eventos de auditoría"
        indexes = [
            models.Index(fields=["entidad", "entidad_id", "fecha"]),
            models.Index(fields=["correlation_id"]),
        ]

    def __str__(self):
        return f"{self.fecha:%Y-%m-%d %H:%M} · {self.accion} · {self.entidad}:{self.entidad_id}"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("La auditoría es inmutable: no se puede modificar un evento existente.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("La auditoría es inmutable: no se puede eliminar un evento.")


class Alerta(models.Model):
    class Tipo(models.TextChoices):
        SIN_CANDIDATOS = "SIN_CANDIDATOS", "Sin candidatos compatibles"
        PROPUESTA_PENDIENTE = "PROPUESTA_PENDIENTE", "Propuesta pendiente"
        PROPUESTA_FALLIDA = "PROPUESTA_FALLIDA", "Propuesta fallida"
        NOTIFICACION_FALLIDA = "NOTIFICACION_FALLIDA", "Notificación fallida"
        AGENDA_SUSPENDIDA = "AGENDA_SUSPENDIDA", "Agenda suspendida"
        DATOS_INCOMPLETOS = "DATOS_INCOMPLETOS", "Datos incompletos"
        DUPLICADO = "DUPLICADO", "Posible duplicado"

    class Estado(models.TextChoices):
        ABIERTA = "ABIERTA", "Abierta"
        EN_REVISION = "EN_REVISION", "En revisión"
        CERRADA = "CERRADA", "Cerrada"

    tipo = models.CharField(max_length=40, choices=Tipo.choices)
    severidad = models.CharField(
        max_length=20,
        choices=[("INFO", "Información"), ("MEDIA", "Media"), ("ALTA", "Alta")],
        default="MEDIA",
    )
    mensaje = models.CharField(max_length=300)
    entidad = models.CharField(max_length=60, blank=True)
    entidad_id = models.CharField(max_length=80, blank=True)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.ABIERTA)
    asignada_a = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="alertas_asignadas",
    )
    correlation_id = models.UUIDField(default=UUID_DEFAULT, db_index=True)
    creada_en = models.DateTimeField(auto_now_add=True)
    resuelta_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["estado", "-creada_en"]
        verbose_name = "alerta operativa"
        verbose_name_plural = "alertas operativas"
        indexes = [models.Index(fields=["estado", "tipo"])]

    def __str__(self):
        return f"[{self.severidad}] {self.mensaje}"


class MensajeNotificacion(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        SIMULADO = "SIMULADO", "Simulado (no enviado)"
        FALLIDO = "FALLIDO", "Fallido"
        DESCARTADO = "DESCARTADO", "Descartado"
        LEIDO = "LEIDO", "Leído en portal"

    class Canal(models.TextChoices):
        PORTAL = "PORTAL", "Portal"
        EMAIL = "EMAIL", "Correo electrónico"
        SMS = "SMS", "SMS"
        WHATSAPP = "WHATSAPP", "WhatsApp"

    uuid = models.UUIDField(default=UUID_DEFAULT, unique=True, editable=False)
    destinatario_tipo = models.CharField(max_length=20, default="PACIENTE")
    destinatario_id = models.CharField(max_length=80, blank=True)
    destinatario_nombre = models.CharField(max_length=180, blank=True)
    destinatario_contacto = models.CharField(max_length=180, blank=True)
    canal = models.CharField(max_length=20, choices=Canal.choices, default=Canal.PORTAL)
    asunto = models.CharField(max_length=180)
    cuerpo = models.TextField()
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDIENTE)
    dedupe_key = models.CharField(max_length=180, unique=True)
    intentos = models.PositiveSmallIntegerField(default=0)
    max_intentos = models.PositiveSmallIntegerField(default=3)
    error = models.CharField(max_length=255, blank=True)
    correlation_id = models.UUIDField(default=UUID_DEFAULT, db_index=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    procesado_en = models.DateTimeField(null=True, blank=True)
    leido_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-creado_en"]
        verbose_name = "mensaje de notificación"
        verbose_name_plural = "mensajes de notificación"
        indexes = [models.Index(fields=["estado", "creado_en"])]

    def __str__(self):
        return f"{self.canal} · {self.asunto} · {self.estado}"


class MetadatoSemilla(models.Model):
    nombre = models.CharField(max_length=80)
    version = models.CharField(max_length=20)
    descripcion = models.CharField(max_length=255, blank=True)
    es_demo = models.BooleanField(default=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "metadato de semilla"
        verbose_name_plural = "metadatos de semilla"

    def __str__(self):
        return f"{self.nombre} v{self.version}"


def registrar_auditoria(
    *,
    actor=None,
    actor_tipo="USUARIO",
    accion: str,
    entidad: str,
    entidad_id="",
    antes=None,
    despues=None,
    motivo="",
    resultado="OK",
    correlation_id=None,
    request=None,
):
    """Registra un evento de auditoría sin datos clínicos completos."""
    ip_hash = ""
    user_agent = ""
    if request is not None:
        ip = request.META.get("REMOTE_ADDR", "")
        if ip:
            import hashlib

            ip_hash = hashlib.sha256(ip.encode("utf-8")).hexdigest()[:64]
        user_agent = request.META.get("HTTP_USER_AGENT", "")[:180]
    return EventoAuditoria.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        actor_tipo=actor_tipo,
        accion=accion,
        entidad=entidad,
        entidad_id=str(entidad_id or ""),
        estado_anterior=_json_seguro(antes),
        estado_nuevo=_json_seguro(despues),
        motivo=motivo,
        resultado=resultado,
        correlation_id=correlation_id or uuid.uuid4(),
        ip_hash=ip_hash,
        user_agent_resumido=user_agent,
    )


def _json_seguro(valor):
    if valor is None:
        return None
    try:
        return json.loads(json.dumps(valor, default=str))
    except (TypeError, ValueError):
        return {"detalle": str(valor)}
