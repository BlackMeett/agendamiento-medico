from django.urls import path

from . import views

urlpatterns = [
    path("", views.inicio, name="portal_inicio"),
    path("solicitudes/", views.solicitudes, name="portal_solicitudes"),
    path("solicitudes/<uuid:uuid>/", views.solicitud_detalle, name="portal_solicitud_detalle"),
    path("ofertas/", views.ofertas, name="portal_ofertas"),
    path("ofertas/<int:pk>/aceptar/", views.oferta_aceptar, name="portal_oferta_aceptar"),
    path("ofertas/<int:pk>/rechazar/", views.oferta_rechazar, name="portal_oferta_rechazar"),
    path("horas/", views.horas, name="portal_horas"),
    path("horas/<int:pk>/cancelar/", views.cita_cancelar, name="portal_cita_cancelar"),
    path("perfil/", views.perfil, name="portal_perfil"),
    path("perfil/preferencias/nueva/", views.preferencia_nueva, name="portal_preferencia_nueva"),
    path(
        "perfil/preferencias/<int:pk>/eliminar/",
        views.preferencia_eliminar,
        name="portal_preferencia_eliminar",
    ),
    path("notificaciones/", views.notificaciones, name="portal_notificaciones"),
    path(
        "notificaciones/<int:pk>/leer/",
        views.notificacion_leer,
        name="portal_notificacion_leer",
    ),
]
