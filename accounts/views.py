from django.contrib.auth import logout
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from gestion.forms import LoginForm


class LoginPersonalizado(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def get_success_url(self):
        perfil = getattr(self.request.user, "perfil", None)
        if perfil and perfil.rol == perfil.Rol.PACIENTE:
            return reverse("portal_inicio")
        return reverse("dashboard")


@require_POST
def salir(request):
    logout(request)
    return redirect("login")
