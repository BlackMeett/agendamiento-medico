from django.urls import path

from . import views

urlpatterns = [
    path("pacientes/", views.pacientes_lista, name="pacientes_lista"),
    path("pacientes/nuevo/", views.paciente_nuevo, name="paciente_nuevo"),
    path("pacientes/<int:pk>/", views.paciente_detalle, name="paciente_detalle"),
    path("pacientes/<int:pk>/editar/", views.paciente_editar, name="paciente_editar"),
    path("pacientes/<int:pk>/preferencias/nueva/", views.preferencia_nueva, name="preferencia_nueva"),
    path(
        "pacientes/<int:pk>/preferencias/<int:pref_pk>/eliminar/",
        views.preferencia_eliminar,
        name="preferencia_eliminar",
    ),
    path("solicitudes/", views.solicitudes_lista, name="solicitudes_lista"),
    path("solicitudes/nueva/", views.solicitud_nueva, name="solicitud_nueva"),
    path("solicitudes/<uuid:uuid>/", views.solicitud_detalle, name="solicitud_detalle"),
    path("solicitudes/<uuid:uuid>/validar/", views.solicitud_validar, name="solicitud_validar"),
    path("solicitudes/<uuid:uuid>/rechazar/", views.solicitud_rechazar, name="solicitud_rechazar"),
    path("solicitudes/<uuid:uuid>/cerrar/", views.solicitud_cerrar, name="solicitud_cerrar"),
    path(
        "solicitudes/<uuid:uuid>/datos-clinicos/",
        views.solicitud_datos_clinicos,
        name="solicitud_datos_clinicos",
    ),
    path("lista-espera/", views.lista_espera, name="lista_espera"),
    path("agendas/", views.agendas_lista, name="agendas_lista"),
    path("agendas/nueva/", views.agenda_nueva, name="agenda_nueva"),
    path("agendas/<int:pk>/", views.agenda_detalle, name="agenda_detalle"),
    path("agendas/<int:pk>/generar/", views.agenda_generar, name="agenda_generar"),
    path("agendas/<int:pk>/publicar/", views.agenda_publicar, name="agenda_publicar"),
    path("agendas/<int:pk>/suspender/", views.agenda_suspender, name="agenda_suspender"),
    path("ofertas/", views.ofertas_lista, name="ofertas_lista"),
    path("ofertas/<int:pk>/", views.oferta_detalle, name="oferta_detalle"),
    path("ofertas/vencer/", views.ofertas_vencer, name="ofertas_vencer"),
    path("propuestas/", views.propuestas_lista, name="propuestas_lista"),
    path("propuestas/<int:pk>/aprobar/", views.propuesta_aprobar, name="propuesta_aprobar"),
    path("propuestas/<int:pk>/rechazar/", views.propuesta_rechazar, name="propuesta_rechazar"),
    path("citas/<int:pk>/", views.cita_detalle, name="cita_detalle"),
    path("citas/<int:pk>/cancelar/", views.cita_cancelar, name="cita_cancelar"),
    path("citas/<int:pk>/atender/", views.cita_atender, name="cita_atender"),
    path("citas/<int:pk>/inasistencia/", views.cita_inasistencia, name="cita_inasistencia"),
]
