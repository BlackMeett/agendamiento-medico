from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def get_perfil(user):
    return getattr(user, "perfil", None)


def funcionario_requerido(view):
    @wraps(view)
    @login_required
    def _wrapped(request, *args, **kwargs):
        perfil = get_perfil(request.user)
        if request.user.is_superuser:
            return view(request, *args, **kwargs)
        if perfil is None or not perfil.activo or not perfil.es_funcionario:
            raise PermissionDenied("Esta sección es solo para funcionarios autorizados.")
        return view(request, *args, **kwargs)

    return _wrapped


def roles_requeridos(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def _wrapped(request, *args, **kwargs):
            perfil = get_perfil(request.user)
            if request.user.is_superuser:
                return view(request, *args, **kwargs)
            if perfil is None or not perfil.activo or perfil.rol not in roles:
                raise PermissionDenied("No tienes permiso para realizar esta acción.")
            return view(request, *args, **kwargs)

        return _wrapped

    return decorator


def paciente_requerido(view):
    @wraps(view)
    @login_required
    def _wrapped(request, *args, **kwargs):
        perfil = get_perfil(request.user)
        if perfil is None or not perfil.activo or perfil.rol != perfil.Rol.PACIENTE:
            raise PermissionDenied("Esta sección es solo para pacientes.")
        return view(request, *args, **kwargs)

    return _wrapped


def admin_requerido(view):
    @wraps(view)
    @login_required
    def _wrapped(request, *args, **kwargs):
        perfil = get_perfil(request.user)
        if not request.user.is_superuser and (perfil is None or perfil.rol != perfil.Rol.ADMIN):
            raise PermissionDenied("Esta acción requiere perfil de administrador.")
        return view(request, *args, **kwargs)

    return _wrapped
