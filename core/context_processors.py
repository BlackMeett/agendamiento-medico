from django.conf import settings


def demo_context(request):
    perfil = getattr(request.user, "perfil", None) if request.user.is_authenticated else None
    alertas = 0
    mensajes_no_leidos = 0
    whatsapp_pendientes = 0
    if perfil and perfil.es_funcionario:
        try:
            from core.models import Alerta

            alertas = Alerta.objects.filter(estado=Alerta.Estado.ABIERTA).count()
        except Exception:
            alertas = 0
        if getattr(perfil, "puede_gestionar_pacientes", False):
            try:
                from core.models import MensajeNotificacion
                from core.scoping import filtrar_pacientes
                from gestion.models import Paciente

                mensajes = MensajeNotificacion.objects.filter(
                    canal=MensajeNotificacion.Canal.WHATSAPP,
                    estado=MensajeNotificacion.Estado.PENDIENTE,
                )
                if not request.user.is_superuser:
                    ids = [
                        str(uuid)
                        for uuid in filtrar_pacientes(
                            Paciente.objects.all(), request.user
                        ).values_list("uuid", flat=True)
                    ]
                    mensajes = mensajes.filter(
                        destinatario_tipo="PACIENTE",
                        destinatario_id__in=ids,
                    )
                whatsapp_pendientes = mensajes.count()
            except Exception:
                whatsapp_pendientes = 0
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
        "WHATSAPP_MODE": getattr(settings, "WHATSAPP_MODE", "SIMULADO"),
        "perfil_actual": perfil,
        "alertas_abiertas": alertas,
        "mensajes_no_leidos": mensajes_no_leidos,
        "whatsapp_pendientes": whatsapp_pendientes,
    }
