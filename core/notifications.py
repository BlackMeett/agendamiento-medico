from __future__ import annotations

import sys
import uuid

from django.utils import timezone

from core.helpers import crear_alerta
from core.models import MensajeNotificacion


def encolar_mensaje(
    *,
    dedupe_key: str,
    destinatario_tipo: str,
    destinatario_id: str,
    destinatario_nombre: str,
    destinatario_contacto: str,
    canal: str,
    asunto: str,
    cuerpo: str,
    correlation_id=None,
    max_intentos: int = 3,
):
    """Outbox: guarda el mensaje en la misma transacción del hecho de negocio."""
    mensaje, creado = MensajeNotificacion.objects.get_or_create(
        dedupe_key=dedupe_key,
        defaults={
            "destinatario_tipo": destinatario_tipo,
            "destinatario_id": str(destinatario_id),
            "destinatario_nombre": destinatario_nombre,
            "destinatario_contacto": destinatario_contacto,
            "canal": canal,
            "asunto": asunto,
            "cuerpo": cuerpo,
            "correlation_id": correlation_id or uuid.uuid4(),
            "max_intentos": max_intentos,
        },
    )
    return mensaje, creado


def despachar_pendientes(limite: int = 100) -> dict:
    """Adaptador simulado. No llama a ningún proveedor externo.

    Los mensajes de portal quedan pendientes hasta que el paciente los lee.
    Los canales externos se marcan SIMULADO, nunca ENVIADO.
    """
    procesados = 0
    fallidos = 0
    pendientes = MensajeNotificacion.objects.filter(
        estado=MensajeNotificacion.Estado.PENDIENTE
    ).order_by("creado_en")[:limite]

    for mensaje in pendientes:
        if mensaje.canal == MensajeNotificacion.Canal.PORTAL:
            continue
        try:
            # Simulación explícita: se registra en consola y en la base.
            print(
                f"[NOTIFICACIÓN SIMULADA] {mensaje.canal} -> "
                f"{mensaje.destinatario_nombre} <{mensaje.destinatario_contacto}>: {mensaje.asunto}",
                file=sys.stdout,
            )
            mensaje.estado = MensajeNotificacion.Estado.SIMULADO
            mensaje.intentos += 1
            mensaje.procesado_en = timezone.now()
            mensaje.error = ""
            mensaje.save(update_fields=["estado", "intentos", "procesado_en", "error"])
            procesados += 1
        except Exception as exc:  # pragma: no cover - defensa del adaptador
            mensaje.intentos += 1
            mensaje.error = str(exc)[:255]
            if mensaje.intentos >= mensaje.max_intentos:
                mensaje.estado = MensajeNotificacion.Estado.FALLIDO
                crear_alerta(
                    tipo="NOTIFICACION_FALLIDA",
                    mensaje=f"No se pudo simular la notificación {mensaje.dedupe_key}",
                    entidad="MensajeNotificacion",
                    entidad_id=mensaje.pk,
                    severidad="MEDIA",
                    correlation=mensaje.correlation_id,
                )
            mensaje.save(update_fields=["estado", "intentos", "error"])
            fallidos += 1

    return {"procesados": procesados, "fallidos": fallidos, "pendientes": pendientes.count()}


def marcar_leido(mensaje: MensajeNotificacion):
    if mensaje.estado in {
        MensajeNotificacion.Estado.PENDIENTE,
        MensajeNotificacion.Estado.SIMULADO,
    }:
        mensaje.estado = MensajeNotificacion.Estado.LEIDO
        mensaje.leido_en = timezone.now()
        mensaje.save(update_fields=["estado", "leido_en"])
