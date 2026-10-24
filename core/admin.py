from django.contrib import admin

from .models import Alerta, EventoAuditoria, MensajeNotificacion, MetadatoSemilla, Parametro


@admin.register(Parametro)
class ParametroAdmin(admin.ModelAdmin):
    list_display = ("clave", "valor", "grupo", "actualizado_en")
    list_filter = ("grupo",)
    search_fields = ("clave", "descripcion")


@admin.register(EventoAuditoria)
class EventoAuditoriaAdmin(admin.ModelAdmin):
    list_display = ("fecha", "accion", "entidad", "entidad_id", "actor", "resultado")
    list_filter = ("accion", "resultado", "actor_tipo")
    search_fields = ("entidad", "entidad_id", "motivo", "actor__username")
    readonly_fields = [campo.name for campo in EventoAuditoria._meta.fields]
    date_hierarchy = "fecha"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Alerta)
class AlertaAdmin(admin.ModelAdmin):
    list_display = ("creada_en", "tipo", "severidad", "mensaje", "estado", "entidad")
    list_filter = ("estado", "tipo", "severidad")
    search_fields = ("mensaje", "entidad", "entidad_id")


@admin.register(MensajeNotificacion)
class MensajeNotificacionAdmin(admin.ModelAdmin):
    list_display = ("creado_en", "canal", "destinatario_nombre", "asunto", "estado", "intentos")
    list_filter = ("estado", "canal")
    search_fields = ("asunto", "destinatario_nombre", "dedupe_key")
    readonly_fields = ("uuid", "creado_en", "procesado_en", "leido_en")


@admin.register(MetadatoSemilla)
class MetadatoSemillaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "version", "es_demo", "fecha")
    readonly_fields = ("fecha",)
