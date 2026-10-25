from __future__ import annotations

import sys

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email

from core.channels import ResultadoEnvio


class ErrorEmail(Exception):
    """Error controlado al preparar o enviar un correo."""


def enviar_email(mensaje) -> ResultadoEnvio:
    """Envía un mensaje del outbox por correo electrónico.

    Modos:
    - SIMULADO: no contacta un servidor SMTP; imprime el mensaje y deja el
      estado SIMULADO.
    - SMTP: usa el backend SMTP de Django configurado por variables de entorno.
    """
    modo = str(getattr(settings, "EMAIL_MODE", "SIMULADO")).upper()

    if modo == "SIMULADO":
        print(
            f"[EMAIL SIMULADO] {mensaje.destinatario_nombre} "
            f"<{mensaje.destinatario_contacto}>: {mensaje.asunto}",
            file=sys.stdout,
        )
        return ResultadoEnvio(estado="SIMULADO")

    if modo != "SMTP":
        raise ErrorEmail(
            f"EMAIL_MODE no reconocido: {modo}. Usa SIMULADO o SMTP."
        )

    destino = str(
        getattr(mensaje, "destinatario_contacto", "") or ""
    ).strip()
    if not destino:
        raise ErrorEmail("El mensaje no tiene un correo válido.")
    try:
        validate_email(destino)
    except ValidationError as exc:
        raise ErrorEmail("El mensaje no tiene un correo válido.") from exc

    asunto = (getattr(mensaje, "asunto", "") or "").strip() or "Notificación"
    cuerpo = (getattr(mensaje, "cuerpo", "") or "").strip() or asunto
    from_email = str(getattr(settings, "DEFAULT_FROM_EMAIL", "") or "").strip()
    if not from_email:
        raise ErrorEmail("Falta DEFAULT_FROM_EMAIL.")

    try:
        enviados = send_mail(
            subject=asunto,
            message=cuerpo,
            from_email=from_email,
            recipient_list=[destino],
            fail_silently=False,
        )
    except Exception as exc:
        raise ErrorEmail(f"No se pudo enviar el correo: {exc}") from exc

    if enviados != 1:
        raise ErrorEmail("El servidor de correo no confirmó el envío.")
    return ResultadoEnvio(estado="ENVIADO", proveedor_id="SMTP")
