from __future__ import annotations

from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import PerfilUsuario
from core.helpers import crear_alerta
from core.models import MetadatoSemilla, Parametro, registrar_auditoria
from core.notifications import despachar_pendientes
from gestion import services
from gestion.models import (
    Agenda,
    DatosClinicosSolicitud,
    Especialidad,
    Establecimiento,
    EventoMotor,
    HistorialEstadoSolicitud,
    HoraMedica,
    Paciente,
    Profesional,
    PropuestaReagendamiento,
    Solicitud,
)

User = get_user_model()
PASSWORD = "Demo12345!"


class Command(BaseCommand):
    help = "Crea datos ficticios para la demostración local. No usar con datos reales."

    def handle(self, *args, **options):
        hoy = timezone.localdate()
        self.stdout.write("Sembrando datos de demostración...")

        hospital = self._establecimiento("HOSP-DEMO", "Hospital Demo", "Hospital", "Santiago")
        cesfam = self._establecimiento("APS-DEMO", "CESFAM Villa Demo", "CESFAM", "Santiago")

        admin = self._usuario("admin@demo.cl", "Administrador", "Demo", PerfilUsuario.Rol.ADMIN, hospital, True)
        some = self._usuario("some@demo.cl", "SOME", "Demo", PerfilUsuario.Rol.SOME, hospital)
        admision = self._usuario("admision@demo.cl", "Admisión", "Demo", PerfilUsuario.Rol.ADMISION, hospital)
        medico_user = self._usuario("medico@demo.cl", "Médico", "Demo", PerfilUsuario.Rol.MEDICO, hospital)
        paciente_user = self._usuario(
            "paciente@demo.cl", "Elena", "Demo Rojas", PerfilUsuario.Rol.PACIENTE, hospital
        )

        for clave, valor, descripcion, grupo in [
            ("oferta.vigencia_horas", "48", "Plazo de respuesta de una oferta en la demo.", "ofertas"),
            ("consulta.duracion_min", "30", "Duración base de una consulta de demo.", "agenda"),
            ("inasistencia.sancion_automatica", "0", "La demo no aplica sanciones automáticas.", "reglas"),
            ("prioridad.regla", "antiguedad", "La demo ordena por antigüedad; no define prioridad clínica.", "reglas"),
        ]:
            Parametro.objects.update_or_create(
                clave=clave,
                defaults={"valor": valor, "descripcion": descripcion, "grupo": grupo},
            )

        cardio = self._especialidad("CARDIO-DEMO", "Cardiología Demo")
        endo = self._especialidad("ENDO-DEMO", "Endocrinología Demo")
        trauma = self._especialidad("TRAUMA-DEMO", "Traumatología Demo")
        oftalmo = self._especialidad("OFTALMO-DEMO", "Oftalmología Demo")

        dra_ana = self._profesional("DEMO-ANA", "Ana", "Demo Pérez", cardio, hospital)
        dr_bruno = self._profesional("DEMO-BRUNO", "Bruno", "Demo Silva", endo, hospital)
        dra_carla = self._profesional("DEMO-CARLA", "Carla", "Demo Torres", trauma, hospital)
        dr_emilio = self._profesional("DEMO-EMILIO", "Emilio", "Demo Rivas", trauma, hospital)
        dr_diego = self._profesional("DEMO-DIEGO", "Diego", "Demo Fuentes", oftalmo, hospital)

        paciente_demo = self._paciente(
            "11111111-1",
            "Elena",
            "Demo Rojas",
            date(1987, 4, 12),
            "+56 9 1111 1111",
            "paciente@demo.cl",
            cesfam,
            paciente_user,
        )
        agenda_cardio = self._agenda(dra_ana, hospital, cardio, hoy, 30)
        agenda_endo = self._agenda(dr_bruno, hospital, endo, hoy, 30)
        agenda_trauma = self._agenda(dra_carla, hospital, trauma, hoy, 30)
        agenda_trauma_alt = self._agenda(dr_emilio, hospital, trauma, hoy, 30)
        agenda_oftalmo = self._agenda(dr_diego, hospital, oftalmo, hoy, 30)

        for agenda in [agenda_cardio, agenda_endo, agenda_trauma, agenda_trauma_alt, agenda_oftalmo]:
            self._preparar_agenda(agenda, some)

        # La demo parte con una sola ficha de paciente y sin solicitudes activas.
        # El paciente crea su primera solicitud desde /portal/solicitar/.
        # Las agendas quedan publicadas con horas disponibles para que el motor
        # pueda generar una oferta inmediata o cuando se ejecute desde el panel.

        despachados = despachar_pendientes()
        MetadatoSemilla.objects.get_or_create(
            nombre="demo-inicial",
            defaults={
                "version": "1.0",
                "descripcion": "Datos ficticios para la demostración académica.",
                "es_demo": True,
            },
        )
        crear_alerta(
            tipo="DATOS_INCOMPLETOS",
            mensaje="Hay datos de contacto ficticios que deben revisarse antes de una prueba de notificación externa.",
            entidad="Paciente",
            entidad_id=paciente_demo.uuid,
            severidad="INFO",
        )
        registrar_auditoria(
            actor=admin,
            accion="SEMILLA_DEMO",
            entidad="Sistema",
            entidad_id="seed_demo",
            motivo="Carga de datos ficticios",
            despues={"pacientes": 1, "agendas": 5, "notificaciones_simuladas": despachados["procesados"]},
        )

        self.stdout.write(self.style.SUCCESS("Datos de demostración cargados."))
        self.stdout.write("")
        self.stdout.write("Paciente de prueba: Elena Demo Rojas / paciente@demo.cl")
        self.stdout.write("Solicita una hora en: /portal/solicitar/")
        self.stdout.write("")
        self.stdout.write("Credenciales (todas usan la misma contraseña):")
        for correo in ["admin@demo.cl", "some@demo.cl", "admision@demo.cl", "medico@demo.cl", "paciente@demo.cl"]:
            self.stdout.write(f"  {correo} / {PASSWORD}")
        self.stdout.write("")
        self.stdout.write("Rutas:")
        self.stdout.write("  /cuenta/login/  Panel interno")
        self.stdout.write("  /portal/        Portal del paciente")
        self.stdout.write("  /admin/         Administración de Django")
        self.stdout.write("")
        self.stdout.write("Los datos son ficticios y las notificaciones externas son simuladas.")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _establecimiento(self, codigo, nombre, tipo, comuna):
        obj, _ = Establecimiento.objects.update_or_create(
            codigo=codigo,
            defaults={"nombre": nombre, "tipo": tipo, "comuna": comuna, "region": "Metropolitana", "activo": True},
        )
        return obj

    def _especialidad(self, codigo, nombre):
        obj, _ = Especialidad.objects.update_or_create(
            codigo=codigo, defaults={"nombre": nombre, "activa": True, "requiere_derivacion": True}
        )
        return obj

    def _usuario(self, username, first_name, last_name, rol, establecimiento, superuser=False):
        user, _ = User.objects.get_or_create(username=username)
        user.email = username
        user.first_name = first_name
        user.last_name = last_name
        user.is_active = True
        user.is_staff = bool(superuser)
        user.is_superuser = bool(superuser)
        user.set_password(PASSWORD)
        user.save()
        PerfilUsuario.objects.update_or_create(
            user=user,
            defaults={"rol": rol, "establecimiento": establecimiento, "activo": True},
        )
        return user

    def _profesional(self, documento, nombres, apellidos, especialidad, establecimiento):
        obj, _ = Profesional.objects.update_or_create(
            documento=documento,
            defaults={
                "nombres": nombres,
                "apellidos": apellidos,
                "especialidad": especialidad,
                "establecimiento": establecimiento,
                "activo": True,
            },
        )
        return obj

    def _paciente(
        self,
        documento,
        nombres,
        apellidos,
        fecha_nacimiento,
        telefono,
        email,
        establecimiento,
        user=None,
    ):
        obj, _ = Paciente.objects.update_or_create(
            tipo_documento=Paciente.TipoDocumento.RUT,
            numero_documento=documento,
            defaults={
                "nombres": nombres,
                "apellidos": apellidos,
                "fecha_nacimiento": fecha_nacimiento,
                "telefono": telefono,
                "email": email,
                "canal_preferido": Paciente.CanalPreferido.PORTAL if user else Paciente.CanalPreferido.EMAIL,
                "consentimiento_notificaciones": True,
                "establecimiento_referencia": establecimiento,
                "estado_contacto": Paciente.EstadoContacto.CONFIRMADO,
                "user": user,
                "activo": True,
            },
        )
        return obj

    def _agenda(self, profesional, establecimiento, especialidad, hoy, duracion):
        existente = (
            Agenda.objects.filter(
                profesional=profesional,
                fecha_fin__gte=hoy,
                estado__in=[Agenda.Estado.BORRADOR, Agenda.Estado.PUBLICADA],
            )
            .order_by("fecha_inicio")
            .first()
        )
        if existente:
            return existente
        return Agenda.objects.create(
            profesional=profesional,
            establecimiento=establecimiento,
            especialidad=especialidad,
            fecha_inicio=hoy + timedelta(days=1),
            fecha_fin=hoy + timedelta(days=10),
            duracion_min=duracion,
            estado=Agenda.Estado.BORRADOR,
        )

    def _preparar_agenda(self, agenda, actor):
        services.generar_horas(
            agenda,
            dias_semana={0, 1, 2, 3, 4},
            hora_inicio=time(9, 0),
            hora_fin=time(12, 0),
            actor=actor,
        )
        if agenda.estado == Agenda.Estado.BORRADOR:
            services.publicar_agenda(agenda, actor=actor)

    def _solicitud(self, referencia, paciente, especialidad, origen, destino, fecha, actor, motivo):
        solicitud, creada = Solicitud.objects.get_or_create(
            referencia_externa=referencia,
            defaults={
                "paciente": paciente,
                "especialidad": especialidad,
                "establecimiento_origen": origen,
                "establecimiento_destino": destino,
                "origen": Solicitud.Origen.APS,
                "estado": Solicitud.Estado.EN_LISTA_ESPERA,
                "fecha_ingreso": fecha,
                "fecha_validacion": fecha,
                "fecha_lista_espera": fecha,
                "observaciones": "Solicitud ficticia de demostración.",
                "creada_por": actor,
            },
        )
        if creada:
            DatosClinicosSolicitud.objects.create(
                solicitud=solicitud,
                motivo_derivacion=motivo,
                diagnostico="Diagnóstico ficticio de demostración",
                notas="Dato clínico simulado. No corresponde a una persona real.",
                actualizado_por=actor,
            )
            HistorialEstadoSolicitud.objects.create(
                solicitud=solicitud,
                estado_anterior="",
                estado_nuevo=Solicitud.Estado.EN_LISTA_ESPERA,
                actor=actor,
                motivo="Semilla de demostración",
            )
        return solicitud

    def _hora_libre(self, agenda, offset=0):
        return (
            HoraMedica.objects.filter(
                bloque__agenda=agenda,
                estado=HoraMedica.Estado.DISPONIBLE,
                inicio__gt=timezone.now(),
                bloque__agenda__estado=Agenda.Estado.PUBLICADA,
            )
            .order_by("inicio")[offset : offset + 1]
            .first()
        )

    def _sembrar_oferta(self, solicitud, agenda, actor, nota):
        if solicitud.ofertas.filter(estado="PENDIENTE").exists():
            return
        if solicitud.citas.filter(estado__in=["CONFIRMADA", "ATENDIDA"]).exists():
            return
        if solicitud.estado != Solicitud.Estado.EN_LISTA_ESPERA:
            return
        # Busca una hora que no esté reservada por otra oferta.
        for offset in range(10):
            hora = self._hora_libre(agenda, offset)
            if not hora:
                break
            try:
                services.crear_oferta_manual(solicitud, hora, actor=actor)
                self.stdout.write(f"  Oferta demo: {solicitud.paciente} · {hora.inicio:%d/%m %H:%M} ({nota})")
                return
            except services.ErrorMotor:
                continue

    def _sembrar_cita(self, solicitud, agenda, actor):
        if solicitud.citas.exists():
            return
        if solicitud.estado != Solicitud.Estado.EN_LISTA_ESPERA:
            return
        for offset in range(10):
            hora = self._hora_libre(agenda, offset)
            if not hora:
                break
            try:
                cita = services.crear_cita_manual(solicitud, hora, actor=actor)
                self.stdout.write(f"  Cita demo: {solicitud.paciente} · {hora.inicio:%d/%m %H:%M}")
                return cita
            except services.ErrorMotor:
                continue

    def _sembrar_propuesta(self, solicitud, agenda_original, agenda_alt, actor):
        cita = self._sembrar_cita(solicitud, agenda_original, actor)
        if not cita:
            return
        if PropuestaReagendamiento.objects.filter(
            cita_original=cita, estado=PropuestaReagendamiento.Estado.PENDIENTE
        ).exists():
            return
        alternativa = self._hora_libre(agenda_alt)
        if not alternativa:
            return
        cita.estado = "REAGENDAMIENTO_PENDIENTE"
        cita.save(update_fields=["estado", "actualizado_en"])
        cita.hora.estado = HoraMedica.Estado.CANCELADA
        cita.hora.motivo_cancelacion = "Ejemplo de suspensión de agenda"
        cita.hora.save(update_fields=["estado", "motivo_cancelacion", "actualizado_en"])
        propuesta = PropuestaReagendamiento.objects.create(
            cita_original=cita,
            solicitud=solicitud,
            hora_propuesta=alternativa,
            estado=PropuestaReagendamiento.Estado.PENDIENTE,
            motivo="Ejemplo de suspensión de agenda por ausencia médica ficticia",
            creada_por_sistema=True,
        )
        crear_alerta(
            tipo="PROPUESTA_PENDIENTE",
            mensaje=f"Propuesta de reagendamiento demo para {solicitud.paciente}.",
            entidad="PropuestaReagendamiento",
            entidad_id=propuesta.uuid,
            severidad="MEDIA",
            correlation=propuesta.correlation_id,
        )
        self.stdout.write(f"  Propuesta demo: {solicitud.paciente} · {alternativa.inicio:%d/%m %H:%M}")
