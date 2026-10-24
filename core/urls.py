from django.urls import path

from . import views

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("panel/", views.dashboard, name="dashboard"),
    path("motor/ejecutar/", views.ejecutar_motor, name="ejecutar_motor"),
    path("notificaciones/", views.notificaciones_lista, name="notificaciones_lista"),
    path("notificaciones/despachar/", views.notificaciones_despachar, name="notificaciones_despachar"),
    path(
        "notificaciones/recordatorios/",
        views.notificaciones_recordatorios,
        name="notificaciones_recordatorios",
    ),
    path(
        "notificaciones/<int:pk>/enviada-manual/",
        views.notificacion_enviada_manual,
        name="notificacion_enviada_manual",
    ),
    path(
        "notificaciones/<int:pk>/reintentar/",
        views.notificacion_reintentar,
        name="notificacion_reintentar",
    ),
    path("alertas/", views.alertas, name="alertas"),
    path("alertas/<int:pk>/cerrar/", views.cerrar_alerta, name="cerrar_alerta"),
    path("alertas/cerrar-sin-candidatos/", views.cerrar_alertas_hora, name="cerrar_alertas_hora"),
    path("auditoria/", views.auditoria, name="auditoria"),
    path("reportes/", views.reportes, name="reportes"),
    path("reportes/exportar/", views.exportar_reporte, name="exportar_reporte"),
    path("health/", views.health, name="health"),
]
