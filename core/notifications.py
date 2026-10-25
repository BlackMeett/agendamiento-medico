from __future__ import annotations

import sys
import uuid

from django.utils import timezone

from core.emails import enviar_email
from core.helpers import crear_alerta
from core.models import MensajeNotificacion
from core.whatsapp import enviar_whatsapp


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


def despachar_pendientes(limite: int = 100, destinatario_ids=None) -> dict:
    """Procesa el outbox de canales externos.

    - PORTAL queda pendiente hasta que el paciente lo lee.
    - WHATSAPP se envía con el adaptador configurado (simulado por defecto).
    - EMAIL usa SMTP si ``EMAIL_MODE=SMTP``; en caso contrario simula.
    - SMS mantiene el adaptador simulado de la demo.

    ``destinatario_ids`` permite limitar el despacho al alcance del usuario.
    Un error de un canal externo deja el mensaje PENDIENTE para reintento
    hasta alcanzar max_intentos; después pasa a FALLIDO y genera una alerta.
    """
    procesados = 0
    fallidos = 0
    consulta = MensajeNotificacion.objects.filter(
        estado=MensajeNotificacion.Estado.PENDIENTE
    )
    if destinatario_ids is not None:
        consulta = consulta.filter(destinatario_id__in=destinatario_ids)
    pendientes = list(consulta.order_by("creado_en")[:limite])

    for mensaje in pendientes:
        if mensaje.canal == MensajeNotificacion.Canal.PORTAL:
            continue
        try:
            if mensaje.canal == MensajeNotificacion.Canal.WHATSAPP:
                resultado = enviar_whatsapp(mensaje)
                mensaje.estado = resultado.estado
                mensaje.proveedor_id = resultado.proveedor_id
            elif mensaje.canal == MensajeNotificacion.Canal.EMAIL:
                resultado = enviar_email(mensaje)
                mensaje.estado = resultado.estado
                mensaje.proveedor_id = resultado.proveedor_id
            else:
                # SMS sigue siendo simulado en esta demo.
                print(
                    f"[NOTIFICACIÓN SIMULADA] {mensaje.canal} -> "
                    f"{mensaje.destinatario_nombre} <{mensaje.destinatario_contacto}>: "
                    f"{mensaje.asunto}",
                    file=sys.stdout,
                )
                mensaje.estado = MensajeNotificacion.Estado.SIMULADO

            mensaje.intentos += 1
            mensaje.procesado_en = timezone.now()
            mensaje.error = ""
            mensaje.save(
                update_fields=[
                    "estado",
                    "proveedor_id",
                    "intentos",
                    "procesado_en",
                    "error",
                ]
            )
            procesados += 1
        except Exception as exc:
            mensaje.intentos += 1
            mensaje.error = str(exc)[:255]
            if mensaje.intentos >= mensaje.max_intentos:
                mensaje.estado = MensajeNotificacion.Estado.FALLIDO
                crear_alerta(
                    tipo="NOTIFICACION_FALLIDA",
                    mensaje=f"No se pudo enviar la notificación {mensaje.dedupe_key}",
                    entidad="MensajeNotificacion",
                    entidad_id=mensaje.pk,
                    severidad="MEDIA",
                    correlation=mensaje.correlation_id,
                )
            mensaje.save(update_fields=["estado", "intentos", "error"])
            fallidos += 1

    return {
        "procesados": procesados,
        "fallidos": fallidos,
        "pendientes": consulta.count(),
    }


def marcar_leido(mensaje: MensajeNotificacion):
    if mensaje.estado in {
        MensajeNotificacion.Estado.PENDIENTE,
        MensajeNotificacion.Estado.SIMULADO,
    }:
        mensaje.estado = MensajeNotificacion.Estado.LEIDO
        mensaje.leido_en = timezone.now()
        mensaje.save(update_fields=["estado", "leido_en"])
