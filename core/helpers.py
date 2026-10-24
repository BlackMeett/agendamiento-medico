from __future__ import annotations

import uuid

from django.utils import timezone

from core.models import Alerta


def correlation_id(valor=None):
    return valor or uuid.uuid4()


def crear_alerta(
    *,
    tipo,
    mensaje,
    entidad="",
    entidad_id="",
    severidad="MEDIA",
    correlation=None,
    asignada_a=None,
):
    """Crea una alerta abierta sin duplicar una ya abierta para la misma entidad."""
    existente = Alerta.objects.filter(
        tipo=tipo,
        entidad=entidad,
        entidad_id=str(entidad_id),
        estado=Alerta.Estado.ABIERTA,
    ).first()
    if existente:
        return existente
    return Alerta.objects.create(
        tipo=tipo,
        mensaje=mensaje[:300],
        entidad=entidad,
        entidad_id=str(entidad_id),
        severidad=severidad,
        correlation_id=correlation or uuid.uuid4(),
        asignada_a=asignada_a,
    )


def resolver_alertas(*, tipo=None, entidad="", entidad_id=""):
    qs = Alerta.objects.filter(estado=Alerta.Estado.ABIERTA)
    if tipo:
        qs = qs.filter(tipo=tipo)
    if entidad:
        qs = qs.filter(entidad=entidad)
    if entidad_id:
        qs = qs.filter(entidad_id=str(entidad_id))
    qs.update(estado=Alerta.Estado.CERRADA, resuelta_en=timezone.now())
