from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from django.conf import settings


class ErrorWhatsApp(Exception):
    """Error controlado al preparar o enviar un mensaje de WhatsApp."""


@dataclass(frozen=True)
class ResultadoEnvio:
    estado: str
    proveedor_id: str = ""


def normalizar_telefono(telefono: str) -> str:
    """Deja solo dígitos y quita el prefijo internacional 00.

    El resultado debe incluir código de país, por ejemplo 56911111111.
    No intenta adivinar el país si el número viene sin código.
    """
    digitos = re.sub(r"\D", "", telefono or "")
    if digitos.startswith("00"):
        digitos = digitos[2:]
    return digitos


def generar_enlace_whatsapp(telefono: str, mensaje: str) -> str:
    """Genera un enlace wa.me que abre el chat con el texto precargado."""
    numero = normalizar_telefono(telefono)
    if not numero:
        return ""
    texto = quote((mensaje or "").strip(), safe="")
    return f"https://wa.me/{numero}?text={texto}"


def _texto_mensaje(mensaje) -> str:
    asunto = (getattr(mensaje, "asunto", "") or "").strip()
    cuerpo = (getattr(mensaje, "cuerpo", "") or "").strip()
    return f"{asunto}\n\n{cuerpo}".strip()


def enviar_whatsapp(mensaje) -> ResultadoEnvio:
    """Envía un mensaje del outbox por WhatsApp.

    Modos:
    - SIMULADO: no sale de la máquina. El portal y la bandeja interna
      muestran el contenido y un enlace wa.me para revisarlo o enviarlo
      manualmente.
    - CLOUD_API: usa WhatsApp Business Cloud API de Meta. Requiere token,
      identificador del número emisor y un destinatario con código de país.
    """
    modo = str(getattr(settings, "WHATSAPP_MODE", "SIMULADO")).upper()

    if modo == "SIMULADO":
        print(
            f"[WHATSAPP SIMULADO] {mensaje.destinatario_nombre} "
            f"<{mensaje.destinatario_contacto}>: {_texto_mensaje(mensaje)}",
            file=sys.stdout,
        )
        return ResultadoEnvio(estado="SIMULADO")

    if modo != "CLOUD_API":
        raise ErrorWhatsApp(
            f"WHATSAPP_MODE no reconocido: {modo}. Usa SIMULADO o CLOUD_API."
        )

    token = str(getattr(settings, "WHATSAPP_CLOUD_API_TOKEN", "") or "").strip()
    phone_number_id = str(
        getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "") or ""
    ).strip()
    if not token or not phone_number_id:
        raise ErrorWhatsApp(
            "Faltan WHATSAPP_CLOUD_API_TOKEN o WHATSAPP_PHONE_NUMBER_ID."
        )

    destino = normalizar_telefono(mensaje.destinatario_contacto)
    if not destino:
        raise ErrorWhatsApp("El mensaje no tiene un teléfono válido.")

    version = str(getattr(settings, "WHATSAPP_API_VERSION", "v23.0") or "v23.0")
    url = f"https://graph.facebook.com/{version}/{phone_number_id}/messages"
    carga = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": destino,
        "type": "text",
        "text": {"preview_url": False, "body": _texto_mensaje(mensaje)},
    }
    solicitud = Request(
        url,
        data=json.dumps(carga).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    timeout = int(getattr(settings, "WHATSAPP_TIMEOUT_SECONDS", 10) or 10)

    try:
        with urlopen(solicitud, timeout=timeout) as respuesta:
            contenido = respuesta.read().decode("utf-8") or "{}"
    except HTTPError as exc:
        detalle = exc.read().decode("utf-8", errors="replace")[:200]
        raise ErrorWhatsApp(f"WhatsApp Cloud API respondió HTTP {exc.code}: {detalle}") from exc
    except URLError as exc:
        raise ErrorWhatsApp(f"No se pudo conectar con WhatsApp Cloud API: {exc.reason}") from exc
    except ValueError as exc:
        raise ErrorWhatsApp("WhatsApp Cloud API devolvió una respuesta inválida.") from exc

    try:
        datos = json.loads(contenido)
    except json.JSONDecodeError as exc:
        raise ErrorWhatsApp("WhatsApp Cloud API devolvió JSON inválido.") from exc

    mensajes = datos.get("messages") or []
    proveedor_id = ""
    if mensajes and isinstance(mensajes[0], dict):
        proveedor_id = str(mensajes[0].get("id", "") or "")
    return ResultadoEnvio(estado="ENVIADO", proveedor_id=proveedor_id)
