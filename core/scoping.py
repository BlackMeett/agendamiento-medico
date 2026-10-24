from __future__ import annotations

from django.db.models import Q


def get_perfil(user):
    return getattr(user, "perfil", None) if getattr(user, "is_authenticated", False) else None


def alcance_establecimiento(user):
    perfil = get_perfil(user)
    if user.is_superuser:
        return None
    if perfil and perfil.rol == perfil.Rol.ADMIN:
        return None
    return getattr(perfil, "establecimiento", None)


def filtrar_pacientes(qs, user):
    establecimiento = alcance_establecimiento(user)
    if not establecimiento:
        return qs
    return qs.filter(
        Q(establecimiento_referencia=establecimiento)
        | Q(solicitudes__establecimiento_origen=establecimiento)
        | Q(solicitudes__establecimiento_destino=establecimiento)
    ).distinct()


def filtrar_solicitudes(qs, user):
    establecimiento = alcance_establecimiento(user)
    if not establecimiento:
        return qs
    return qs.filter(
        Q(establecimiento_origen=establecimiento) | Q(establecimiento_destino=establecimiento)
    ).distinct()


def filtrar_agendas(qs, user):
    establecimiento = alcance_establecimiento(user)
    if not establecimiento:
        return qs
    return qs.filter(establecimiento=establecimiento)


def filtrar_ofertas(qs, user):
    establecimiento = alcance_establecimiento(user)
    if not establecimiento:
        return qs
    return qs.filter(
        Q(hora__bloque__agenda__establecimiento=establecimiento)
        | Q(solicitud__establecimiento_origen=establecimiento)
        | Q(solicitud__establecimiento_destino=establecimiento)
    ).distinct()


def filtrar_citas(qs, user):
    establecimiento = alcance_establecimiento(user)
    if not establecimiento:
        return qs
    return qs.filter(
        Q(hora__bloque__agenda__establecimiento=establecimiento)
        | Q(solicitud__establecimiento_origen=establecimiento)
        | Q(solicitud__establecimiento_destino=establecimiento)
    ).distinct()


def puede_ver_paciente(user, paciente):
    if user.is_superuser:
        return True
    perfil = get_perfil(user)
    if perfil is None:
        return False
    if perfil.rol == perfil.Rol.ADMIN:
        return True
    if perfil.rol == perfil.Rol.PACIENTE:
        return getattr(paciente, "user_id", None) == user.id
    establecimiento = perfil.establecimiento
    if not establecimiento:
        return True
    return (
        paciente.establecimiento_referencia_id == establecimiento.id
        or paciente.solicitudes.filter(
            Q(establecimiento_origen=establecimiento) | Q(establecimiento_destino=establecimiento)
        ).exists()
    )


def puede_ver_solicitud(user, solicitud):
    if user.is_superuser:
        return True
    perfil = get_perfil(user)
    if perfil is None:
        return False
    if perfil.rol == perfil.Rol.ADMIN:
        return True
    if perfil.rol == perfil.Rol.PACIENTE:
        return solicitud.paciente.user_id == user.id
    establecimiento = perfil.establecimiento
    if not establecimiento:
        return True
    return (
        solicitud.establecimiento_origen_id == establecimiento.id
        or solicitud.establecimiento_destino_id == establecimiento.id
        or solicitud.paciente.establecimiento_referencia_id == establecimiento.id
    )
