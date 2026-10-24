from django.contrib import admin

from .models import (
    Agenda,
    BloqueAgenda,
    Cita,
    DatosClinicosSolicitud,
    Especialidad,
    Establecimiento,
    EventoMotor,
    HistorialEstadoSolicitud,
    HoraMedica,
    OfertaHora,
    Paciente,
    PreferenciaDisponibilidad,
    Profesional,
    PropuestaReagendamiento,
    Solicitud,
)


@admin.register(Establecimiento)
class EstablecimientoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "codigo", "tipo", "comuna", "activo")
    search_fields = ("nombre", "codigo", "comuna")


@admin.register(Especialidad)
class EspecialidadAdmin(admin.ModelAdmin):
    list_display = ("nombre", "codigo", "activa", "requiere_derivacion")
    search_fields = ("nombre", "codigo")


@admin.register(Profesional)
class ProfesionalAdmin(admin.ModelAdmin):
    list_display = ("apellidos", "nombres", "especialidad", "establecimiento", "activo")
    list_filter = ("especialidad", "establecimiento", "activo")
    search_fields = ("nombres", "apellidos", "documento")


@admin.register(Paciente)
class PacienteAdmin(admin.ModelAdmin):
    list_display = ("apellidos", "nombres", "tipo_documento", "numero_documento", "establecimiento_referencia", "activo")
    list_filter = ("tipo_documento", "estado_contacto", "establecimiento_referencia", "activo")
    search_fields = ("nombres", "apellidos", "numero_documento", "email")
    raw_id_fields = ("user",)


@admin.register(PreferenciaDisponibilidad)
class PreferenciaAdmin(admin.ModelAdmin):
    list_display = ("paciente", "dia_semana", "hora_desde", "hora_hasta", "es_restriccion", "vigente")
    list_filter = ("dia_semana", "es_restriccion", "vigente")


@admin.register(Solicitud)
class SolicitudAdmin(admin.ModelAdmin):
    list_display = ("uuid", "paciente", "especialidad", "estado", "fecha_ingreso", "establecimiento_origen")
    list_filter = ("estado", "especialidad", "establecimiento_origen")
    search_fields = ("uuid", "paciente__nombres", "paciente__apellidos", "paciente__numero_documento")
    raw_id_fields = ("paciente", "creada_por")


@admin.register(DatosClinicosSolicitud)
class DatosClinicosAdmin(admin.ModelAdmin):
    list_display = ("solicitud", "diagnostico", "actualizado_en")
    search_fields = ("solicitud__uuid", "diagnostico")


@admin.register(HistorialEstadoSolicitud)
class HistorialAdmin(admin.ModelAdmin):
    list_display = ("solicitud", "estado_anterior", "estado_nuevo", "fecha", "actor")
    list_filter = ("estado_nuevo",)
    readonly_fields = ("fecha",)


@admin.register(Agenda)
class AgendaAdmin(admin.ModelAdmin):
    list_display = ("profesional", "especialidad", "fecha_inicio", "fecha_fin", "estado")
    list_filter = ("estado", "especialidad", "establecimiento")
    date_hierarchy = "fecha_inicio"


@admin.register(BloqueAgenda)
class BloqueAdmin(admin.ModelAdmin):
    list_display = ("agenda", "fecha", "hora_inicio", "hora_fin", "estado")
    list_filter = ("estado", "fecha")


@admin.register(HoraMedica)
class HoraMedicaAdmin(admin.ModelAdmin):
    list_display = ("inicio", "fin", "estado", "bloque")
    list_filter = ("estado",)
    date_hierarchy = "inicio"


@admin.register(OfertaHora)
class OfertaAdmin(admin.ModelAdmin):
    list_display = ("uuid", "solicitud", "hora", "estado", "expira_en", "intento", "creada_por_sistema")
    list_filter = ("estado", "creada_por_sistema")
    search_fields = ("uuid", "solicitud__uuid")


@admin.register(Cita)
class CitaAdmin(admin.ModelAdmin):
    list_display = ("uuid", "solicitud", "hora", "estado", "confirmada_en", "registrada_por")
    list_filter = ("estado",)
    search_fields = ("uuid", "solicitud__uuid")


@admin.register(PropuestaReagendamiento)
class PropuestaAdmin(admin.ModelAdmin):
    list_display = ("uuid", "solicitud", "cita_original", "hora_propuesta", "estado", "creado_en")
    list_filter = ("estado",)
    readonly_fields = ("uuid", "creado_en", "actualizado_en")


@admin.register(EventoMotor)
class EventoMotorAdmin(admin.ModelAdmin):
    list_display = ("tipo", "entidad_tipo", "entidad_id", "estado", "intentos", "creado_en")
    list_filter = ("estado", "tipo")
    readonly_fields = ("idempotency_key", "creado_en", "actualizado_en", "procesado_en")
