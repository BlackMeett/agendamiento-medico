from django.urls import path

from . import views

urlpatterns = [
    path("login/", views.LoginPersonalizado.as_view(), name="login"),
    path("logout/", views.salir, name="logout"),
]
