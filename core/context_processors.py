from django.conf import settings


def demo_context(request):
    perfil = getattr(request.user, "perfil", None) if request.user.is_authenticated else None
    alertas = 0
    mensajes_no_leidos = 0
    if perfil and perfil.es_funcionario:
        try:
            from core.models import Alerta

            alertas = Alerta.objects.filter(estado=Alerta.Estado.ABIERTA).count()
        except Exception:
            alertas = 0
    elif perfil and perfil.rol == perfil.Rol.PACIENTE:
        try:
            from core.models import MensajeNotificacion
            from gestion.models import Paciente

            paciente = Paciente.objects.filter(user=request.user).first()
            if paciente:
                mensajes_no_leidos = MensajeNotificacion.objects.filter(
                    destinatario_tipo="PACIENTE",
                    destinatario_id=str(paciente.uuid),
                    estado__in=[
                        MensajeNotificacion.Estado.PENDIENTE,
                        MensajeNotificacion.Estado.SIMULADO,
                    ],
                ).count()
        except Exception:
            mensajes_no_leidos = 0
    return {
        "DEMO_MODE": getattr(settings, "DEMO_MODE", True),
        "DEMO_BANNER": getattr(settings, "DEMO_BANNER", ""),
        "perfil_actual": perfil,
        "alertas_abiertas": alertas,
        "mensajes_no_leidos": mensajes_no_leidos,
    }
