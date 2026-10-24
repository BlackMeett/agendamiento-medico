from django.urls import path

from . import views

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("panel/", views.dashboard, name="dashboard"),
    path("motor/ejecutar/", views.ejecutar_motor, name="ejecutar_motor"),
    path("alertas/", views.alertas, name="alertas"),
    path("alertas/<int:pk>/cerrar/", views.cerrar_alerta, name="cerrar_alerta"),
    path("alertas/cerrar-sin-candidatos/", views.cerrar_alertas_hora, name="cerrar_alertas_hora"),
    path("auditoria/", views.auditoria, name="auditoria"),
    path("reportes/", views.reportes, name="reportes"),
    path("reportes/exportar/", views.exportar_reporte, name="exportar_reporte"),
    path("health/", views.health, name="health"),
]
