from __future__ import annotations

from datetime import datetime, time, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import PerfilUsuario
from core.models import Alerta, EventoAuditoria, MensajeNotificacion
from core.notifications import despachar_pendientes, encolar_mensaje
from gestion import services
from gestion.forms import SolicitudForm
from gestion.models import (
    Agenda,
    BloqueAgenda,
    Cita,
    Especialidad,
    Establecimiento,
    EventoMotor,
    HoraMedica,
    OfertaHora,
    Paciente,
    Profesional,
    PropuestaReagendamiento,
    Solicitud,
)

User = get_user_model()


class BaseEngineTest(TestCase):
    def setUp(self):
        self.hoy = timezone.localdate()
        self.est = Establecimiento.objects.create(codigo="EST1", nombre="Establecimiento Uno")
        self.est2 = Establecimiento.objects.create(codigo="EST2", nombre="Establecimiento Dos")
        self.esp = Especialidad.objects.create(codigo="ESP1", nombre="Especialidad Demo")
        self.esp2 = Especialidad.objects.create(codigo="ESP2", nombre="Otra Especialidad")
        self.prof = Profesional.objects.create(
            nombres="Profesional",
            apellidos="Demo",
            documento="PROF1",
            especialidad=self.esp,
            establecimiento=self.est,
        )
        self.agenda = Agenda.objects.create(
            profesional=self.prof,
            establecimiento=self.est,
            especialidad=self.esp,
            fecha_inicio=self.hoy + timedelta(days=1),
            fecha_fin=self.hoy + timedelta(days=1),
            duracion_min=30,
            estado=Agenda.Estado.PUBLICADA,
        )
        self.bloque = BloqueAgenda.objects.create(
            agenda=self.agenda,
            fecha=self.hoy + timedelta(days=1),
            hora_inicio=time(9, 0),
            hora_fin=time(10, 0),
        )
        self.hora = self._hora(9, 0)
        self.hora2 = self._hora(9, 30)
        self.p1 = self._paciente("P1", "Ana", "Uno")
        self.p2 = self._paciente("P2", "Beto", "Dos")
        self.s1 = self._solicitud(self.p1, self.esp, self.hoy - timedelta(days=5))
        self.s2 = self._solicitud(self.p2, self.esp, self.hoy - timedelta(days=1))
        self.user = User.objects.create_user(username="operador", password="Demo12345!")

    def _hora(self, hora, minuto=0):
        inicio = timezone.make_aware(
            datetime.combine(self.hoy + timedelta(days=1), time(hora, minuto))
        )
        return HoraMedica.objects.create(
            bloque=self.bloque,
            inicio=inicio,
            fin=inicio + timedelta(minutes=30),
        )

    def _paciente(self, documento, nombres, apellidos, user=None, canal="PORTAL"):
        return Paciente.objects.create(
            tipo_documento=Paciente.TipoDocumento.RUT,
            numero_documento=documento,
            nombres=nombres,
            apellidos=apellidos,
            fecha_nacimiento=self.hoy - timedelta(days=30 * 365),
            telefono="+56 9 0000 0000",
            email=f"{documento.lower()}@demo.cl",
            canal_preferido=canal,
            establecimiento_referencia=self.est,
            user=user,
        )

    def _solicitud(self, paciente, especialidad, fecha, estado=Solicitud.Estado.EN_LISTA_ESPERA):
        return Solicitud.objects.create(
            paciente=paciente,
            especialidad=especialidad,
            establecimiento_origen=self.est,
            establecimiento_destino=self.est,
            estado=estado,
            fecha_ingreso=fecha,
            fecha_lista_espera=fecha if estado == Solicitud.Estado.EN_LISTA_ESPERA else None,
        )

    def _crear_cita(self, solicitud=None):
        solicitud = solicitud or self.s1
        oferta = services.ofrecer_hora(self.hora.pk, actor=self.user)
        return services.aceptar_oferta(oferta.pk, actor=self.user)


class EngineTests(BaseEngineTest):
    def test_prioridad_por_antiguedad(self):
        oferta = services.ofrecer_hora(self.hora.pk, actor=self.user)
        self.assertEqual(oferta.solicitud, self.s1)
        self.assertEqual(self.s1.dias_espera, 5)

    def test_aceptar_crea_cita_y_ocupa_hora(self):
        cita = self._crear_cita()
        self.assertEqual(cita.estado, Cita.Estado.CONFIRMADA)
        self.hora.refresh_from_db()
        self.s1.refresh_from_db()
        self.assertEqual(self.hora.estado, HoraMedica.Estado.OCUPADA)
        self.assertEqual(self.s1.estado, Solicitud.Estado.AGENDADA)

    def test_aceptar_dos_veces_devuelve_la_misma_cita(self):
        cita = self._crear_cita()
        oferta = OfertaHora.objects.get(solicitud=self.s1, estado=OfertaHora.Estado.ACEPTADA)
        cita2 = services.aceptar_oferta(oferta.pk, actor=self.user)
        self.assertEqual(cita.pk, cita2.pk)
        self.assertEqual(Cita.objects.filter(solicitud=self.s1).count(), 1)

    def test_rechazar_libera_y_ofrece_al_siguiente(self):
        oferta = services.ofrecer_hora(self.hora.pk, actor=self.user)
        self.assertEqual(oferta.solicitud, self.s1)
        services.rechazar_oferta(oferta.pk, actor=self.user, motivo="No puede")
        self.assertEqual(
            OfertaHora.objects.filter(estado=OfertaHora.Estado.PENDIENTE).count(), 1
        )
        nueva = OfertaHora.objects.get(estado=OfertaHora.Estado.PENDIENTE)
        self.assertEqual(nueva.solicitud, self.s2)
        self.s1.refresh_from_db()
        self.assertEqual(self.s1.estado, Solicitud.Estado.EN_LISTA_ESPERA)

    def test_vencimiento_libera_y_ofrece_al_siguiente(self):
        oferta = services.ofrecer_hora(self.hora.pk, actor=self.user)
        OfertaHora.objects.filter(pk=oferta.pk).update(
            expira_en=timezone.now() - timedelta(minutes=1)
        )
        cantidad = services.vencer_ofertas()
        self.assertEqual(cantidad, 1)
        oferta.refresh_from_db()
        self.assertEqual(oferta.estado, OfertaHora.Estado.VENCIDA)
        nueva = OfertaHora.objects.get(estado=OfertaHora.Estado.PENDIENTE)
        self.assertEqual(nueva.solicitud, self.s2)

    def test_sin_candidatos_crea_alerta(self):
        Solicitud.objects.filter(pk__in=[self.s1.pk, self.s2.pk]).update(especialidad=self.esp2)
        oferta = services.ofrecer_hora(self.hora.pk, actor=self.user)
        self.assertIsNone(oferta)
        self.assertTrue(Alerta.objects.filter(tipo=Alerta.Tipo.SIN_CANDIDATOS).exists())
        self.hora.refresh_from_db()
        self.assertEqual(self.hora.estado, HoraMedica.Estado.DISPONIBLE)

    def test_solicitud_cerrada_no_es_candidata(self):
        Solicitud.objects.filter(pk__in=[self.s1.pk, self.s2.pk]).update(
            estado=Solicitud.Estado.CERRADA
        )
        oferta = services.ofrecer_hora(self.hora.pk, actor=self.user)
        self.assertIsNone(oferta)
        self.assertEqual(OfertaHora.objects.count(), 0)

    def test_bloque_bloqueado_no_ofrece(self):
        self.bloque.estado = BloqueAgenda.Estado.BLOQUEADO
        self.bloque.save(update_fields=["estado"])
        with self.assertRaises(services.ErrorMotor):
            services.ofrecer_hora(self.hora.pk, actor=self.user)
        self.assertEqual(OfertaHora.objects.count(), 0)

    def test_agenda_suspendida_no_ofrece(self):
        self.agenda.estado = Agenda.Estado.SUSPENDIDA
        self.agenda.save(update_fields=["estado"])
        with self.assertRaises(services.ErrorMotor):
            services.ofrecer_hora(self.hora.pk, actor=self.user)
        self.assertEqual(OfertaHora.objects.count(), 0)

    def test_oferta_duplicada_es_rechazada(self):
        services.ofrecer_hora(self.hora.pk, actor=self.user)
        with self.assertRaises(services.ErrorMotor):
            services.ofrecer_hora(self.hora.pk, actor=self.user)
        self.assertEqual(OfertaHora.objects.count(), 1)

    def test_aceptar_oferta_vencida_falla_y_reoferta(self):
        oferta = services.ofrecer_hora(self.hora.pk, actor=self.user)
        OfertaHora.objects.filter(pk=oferta.pk).update(
            expira_en=timezone.now() - timedelta(minutes=1)
        )
        with self.assertRaises(services.ErrorMotor):
            services.aceptar_oferta(oferta.pk, actor=self.user)
        oferta.refresh_from_db()
        self.hora.refresh_from_db()
        self.s1.refresh_from_db()
        self.assertEqual(oferta.estado, OfertaHora.Estado.VENCIDA)
        self.assertEqual(self.hora.estado, HoraMedica.Estado.OFRECIDA)
        self.assertEqual(self.s1.estado, Solicitud.Estado.EN_LISTA_ESPERA)
        nueva = OfertaHora.objects.get(estado=OfertaHora.Estado.PENDIENTE)
        self.assertEqual(nueva.solicitud, self.s2)

    def test_inasistencia_no_aplica_sancion(self):
        cita = self._crear_cita()
        services.registrar_inasistencia(cita.pk, actor=self.user)
        cita.refresh_from_db()
        self.s1.refresh_from_db()
        self.assertEqual(cita.estado, Cita.Estado.NO_ASISTIO)
        self.assertEqual(self.s1.estado, Solicitud.Estado.EN_LISTA_ESPERA)

    def test_atencion_registra_estado(self):
        cita = self._crear_cita()
        services.marcar_atendida(cita.pk, actor=self.user)
        cita.refresh_from_db()
        self.s1.refresh_from_db()
        self.assertEqual(cita.estado, Cita.Estado.ATENDIDA)
        self.assertEqual(self.s1.estado, Solicitud.Estado.ATENDIDA)

    def test_evento_idempotente(self):
        evento1 = services.crear_evento(
            tipo="HORA_LIBERADA",
            entidad_tipo="HoraMedica",
            entidad_id=self.hora.pk,
            idempotency_key="prueba:evento:1",
        )
        evento2 = services.crear_evento(
            tipo="HORA_LIBERADA",
            entidad_tipo="HoraMedica",
            entidad_id=self.hora.pk,
            idempotency_key="prueba:evento:1",
        )
        self.assertEqual(evento1.pk, evento2.pk)
        self.assertEqual(EventoMotor.objects.count(), 1)

    def test_evento_fallido_persiste_y_alerta(self):
        evento = services.crear_evento(
            tipo="HORA_LIBERADA",
            entidad_tipo="HoraMedica",
            entidad_id=999999,
            idempotency_key="prueba:evento:fallido",
        )
        with self.assertRaises(services.ErrorMotor):
            services.procesar_evento(evento)
        evento.refresh_from_db()
        self.assertEqual(evento.estado, EventoMotor.Estado.FALLIDO)
        self.assertTrue(evento.error)
        self.assertTrue(Alerta.objects.filter(entidad="EventoMotor", entidad_id=str(evento.pk)).exists())

    def test_notificacion_simulada_y_auditoria(self):
        self.p1.canal_preferido = Paciente.CanalPreferido.EMAIL
        self.p1.save(update_fields=["canal_preferido"])
        services.ofrecer_hora(self.hora.pk, actor=self.user)
        self.assertTrue(EventoAuditoria.objects.filter(accion="OFERTA_CREADA").exists())
        self.assertTrue(
            MensajeNotificacion.objects.filter(
                destinatario_id=str(self.p1.uuid), canal="EMAIL", estado="PENDIENTE"
            ).exists()
        )
        despachar_pendientes()
        self.assertTrue(
            MensajeNotificacion.objects.filter(
                destinatario_id=str(self.p1.uuid), canal="EMAIL", estado="SIMULADO"
            ).exists()
        )
        self.assertFalse(
            MensajeNotificacion.objects.filter(
                destinatario_id=str(self.p1.uuid), canal="EMAIL", estado="FALLIDO"
            ).exists()
        )


class WhatsAppNotificationTests(BaseEngineTest):
    def setUp(self):
        super().setUp()
        self.p1.canal_preferido = Paciente.CanalPreferido.WHATSAPP
        self.p1.save(update_fields=["canal_preferido"])

    @override_settings(WHATSAPP_MODE="SIMULADO")
    def test_oferta_y_confirmacion_generan_whatsapp_simulado(self):
        cita = self._crear_cita()
        mensajes = MensajeNotificacion.objects.filter(
            destinatario_id=str(self.p1.uuid), canal="WHATSAPP"
        )
        self.assertEqual(mensajes.count(), 2)
        oferta_msg = mensajes.get(dedupe_key__endswith=":creada:WHATSAPP")
        self.assertIn("https://wa.me/56900000000?text=", oferta_msg.enlace_whatsapp)
        self.assertEqual(oferta_msg.estado, MensajeNotificacion.Estado.PENDIENTE)

        resultado = despachar_pendientes()
        self.assertEqual(resultado["procesados"], 2)
        self.assertEqual(
            mensajes.filter(estado=MensajeNotificacion.Estado.SIMULADO).count(), 2
        )
        self.assertTrue(Cita.objects.filter(pk=cita.pk).exists())

    @override_settings(
        WHATSAPP_MODE="CLOUD_API",
        WHATSAPP_CLOUD_API_TOKEN="token-demo",
        WHATSAPP_PHONE_NUMBER_ID="123456",
    )
    @patch("core.whatsapp.urlopen")
    def test_cloud_api_marca_enviado_y_guarda_id(self, urlopen_mock):
        class Respuesta:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b'{"messages": [{"id": "wamid.demo.123"}]}'

        urlopen_mock.return_value = Respuesta()
        services.ofrecer_hora(self.hora.pk, actor=self.user)
        resultado = despachar_pendientes()

        self.assertEqual(resultado["procesados"], 1)
        mensaje = MensajeNotificacion.objects.get(
            destinatario_id=str(self.p1.uuid), canal="WHATSAPP"
        )
        self.assertEqual(mensaje.estado, MensajeNotificacion.Estado.ENVIADO)
        self.assertEqual(mensaje.proveedor_id, "wamid.demo.123")
        self.assertEqual(mensaje.error, "")
        solicitud_http = urlopen_mock.call_args.args[0]
        self.assertIn("/123456/messages", solicitud_http.full_url)
        self.assertIn(b'"to": "56900000000"', solicitud_http.data)

    @override_settings(
        WHATSAPP_MODE="CLOUD_API",
        WHATSAPP_CLOUD_API_TOKEN="",
        WHATSAPP_PHONE_NUMBER_ID="",
    )
    def test_cloud_api_sin_credenciales_reintenta_y_alerta(self):
        services.ofrecer_hora(self.hora.pk, actor=self.user)
        for _ in range(3):
            despachar_pendientes()
        mensaje = MensajeNotificacion.objects.get(
            destinatario_id=str(self.p1.uuid), canal="WHATSAPP"
        )
        self.assertEqual(mensaje.estado, MensajeNotificacion.Estado.FALLIDO)
        self.assertIn("Faltan WHATSAPP_CLOUD_API_TOKEN", mensaje.error)
        self.assertTrue(
            Alerta.objects.filter(
                tipo="NOTIFICACION_FALLIDA", entidad_id=mensaje.pk
            ).exists()
        )

    @override_settings(WHATSAPP_MODE="SIMULADO")
    def test_rechazo_de_solicitud_notifica_motivo(self):
        solicitud = self._solicitud(
            self.p1,
            self.esp,
            self.hoy,
            estado=Solicitud.Estado.INGRESADA,
        )
        services.rechazar_solicitud(
            solicitud, actor=self.user, motivo="Sin cupo en la especialidad"
        )
        mensaje = MensajeNotificacion.objects.get(
            dedupe_key=f"solicitud:{solicitud.uuid}:rechazada:WHATSAPP"
        )
        self.assertEqual(mensaje.canal, "WHATSAPP")
        self.assertIn("Sin cupo en la especialidad", mensaje.cuerpo)

    @override_settings(WHATSAPP_MODE="SIMULADO")
    def test_cancelacion_de_cita_notifica_motivo(self):
        cita = self._crear_cita()
        services.cancelar_cita(
            cita.pk, actor=self.user, motivo="Cambio de disponibilidad"
        )
        mensaje = MensajeNotificacion.objects.get(
            dedupe_key=f"cita:{cita.uuid}:cancelada:WHATSAPP"
        )
        self.assertEqual(mensaje.canal, "WHATSAPP")
        self.assertIn("Cambio de disponibilidad", mensaje.cuerpo)

    @override_settings(WHATSAPP_MODE="SIMULADO")
    def test_recordatorio_24h_es_idempotente(self):
        cita = self._crear_cita()
        referencia = cita.hora.inicio - timedelta(hours=12)

        self.assertEqual(
            services.crear_recordatorios_proximos(ahora_ref=referencia), 1
        )
        self.assertEqual(
            services.crear_recordatorios_proximos(ahora_ref=referencia), 0
        )
        self.assertEqual(
            MensajeNotificacion.objects.filter(
                dedupe_key=f"cita:{cita.uuid}:recordatorio24h:WHATSAPP"
            ).count(),
            1,
        )

    @override_settings(WHATSAPP_MODE="SIMULADO")
    def test_recordatorio_fuera_de_ventana_no_se_crea(self):
        cita = self._crear_cita()
        referencia = cita.hora.inicio - timedelta(hours=25)
        self.assertEqual(
            services.crear_recordatorios_proximos(ahora_ref=referencia), 0
        )


class ManualBookingTests(BaseEngineTest):
    def test_no_permite_dos_citas_para_la_misma_hora(self):
        services.crear_cita_manual(self.s1, self.hora, actor=self.user)

        with self.assertRaises(services.ErrorMotor):
            services.crear_cita_manual(self.s2, self.hora, actor=self.user)

        self.assertEqual(Cita.objects.filter(hora=self.hora).count(), 1)

    def test_no_permite_cita_superpuesta_del_mismo_paciente(self):
        services.crear_cita_manual(self.s1, self.hora, actor=self.user)
        hora_solapada = HoraMedica.objects.create(
            bloque=self.bloque,
            inicio=self.hora.inicio + timedelta(minutes=15),
            fin=self.hora.inicio + timedelta(minutes=45),
        )
        otra_solicitud = self._solicitud(
            self.p1, self.esp, self.hoy - timedelta(days=2)
        )

        with self.assertRaises(services.ErrorMotor):
            services.crear_cita_manual(otra_solicitud, hora_solapada, actor=self.user)

        self.assertFalse(Cita.objects.filter(solicitud=otra_solicitud).exists())

    def test_no_permite_hora_de_otra_especialidad(self):
        otra_solicitud = self._solicitud(
            self.p1, self.esp2, self.hoy - timedelta(days=2)
        )

        with self.assertRaises(services.ErrorMotor):
            services.crear_cita_manual(otra_solicitud, self.hora, actor=self.user)

        self.assertFalse(Cita.objects.filter(solicitud=otra_solicitud).exists())


class ReschedulingTests(BaseEngineTest):
    def test_suspension_genera_propuesta_y_aprobacion_crea_cita(self):
        cita = self._crear_cita()
        agenda_alt = Agenda.objects.create(
            profesional=Profesional.objects.create(
                nombres="Otro",
                apellidos="Demo",
                documento="PROF2",
                especialidad=self.esp,
                establecimiento=self.est,
            ),
            establecimiento=self.est,
            especialidad=self.esp,
            fecha_inicio=self.hoy + timedelta(days=2),
            fecha_fin=self.hoy + timedelta(days=2),
            duracion_min=30,
            estado=Agenda.Estado.PUBLICADA,
        )
        bloque_alt = BloqueAgenda.objects.create(
            agenda=agenda_alt,
            fecha=self.hoy + timedelta(days=2),
            hora_inicio=time(10, 0),
            hora_fin=time(11, 0),
        )
        inicio_alt = timezone.make_aware(
            datetime.combine(self.hoy + timedelta(days=2), time(10, 0))
        )
        hora_alt = HoraMedica.objects.create(
            bloque=bloque_alt, inicio=inicio_alt, fin=inicio_alt + timedelta(minutes=30)
        )

        resultado = services.suspender_agenda(
            self.agenda, actor=self.user, motivo="Ausencia médica ficticia"
        )
        self.assertEqual(resultado["creadas"], 1)
        propuesta = PropuestaReagendamiento.objects.get(
            estado=PropuestaReagendamiento.Estado.PENDIENTE
        )
        self.assertEqual(propuesta.hora_propuesta, hora_alt)
        cita.refresh_from_db()
        self.assertEqual(cita.estado, Cita.Estado.REAGENDAMIENTO_PENDIENTE)
        self.assertTrue(
            MensajeNotificacion.objects.filter(
                dedupe_key=f"reagendamiento:{propuesta.uuid}:propuesta:PORTAL"
            ).exists()
        )

        nueva = services.aprobar_propuesta(propuesta.pk, actor=self.user, motivo="Aprobada")
        cita.refresh_from_db()
        propuesta.refresh_from_db()
        hora_alt.refresh_from_db()
        self.assertEqual(nueva.estado, Cita.Estado.CONFIRMADA)
        self.assertEqual(cita.estado, Cita.Estado.REAGENDADA)
        self.assertEqual(propuesta.estado, PropuestaReagendamiento.Estado.APROBADA)
        self.assertEqual(hora_alt.estado, HoraMedica.Estado.OCUPADA)
        self.assertTrue(
            MensajeNotificacion.objects.filter(
                dedupe_key=f"reagendamiento:{propuesta.uuid}:aprobado:PORTAL"
            ).exists()
        )

    def test_aprobacion_propuesta_fallida_persiste(self):
        cita = self._crear_cita()
        agenda_alt = Agenda.objects.create(
            profesional=Profesional.objects.create(
                nombres="Tercero",
                apellidos="Demo",
                documento="PROF3",
                especialidad=self.esp,
                establecimiento=self.est,
            ),
            establecimiento=self.est,
            especialidad=self.esp,
            fecha_inicio=self.hoy + timedelta(days=3),
            fecha_fin=self.hoy + timedelta(days=3),
            duracion_min=30,
            estado=Agenda.Estado.PUBLICADA,
        )
        bloque_alt = BloqueAgenda.objects.create(
            agenda=agenda_alt,
            fecha=self.hoy + timedelta(days=3),
            hora_inicio=time(11, 0),
            hora_fin=time(12, 0),
        )
        inicio_alt = timezone.make_aware(
            datetime.combine(self.hoy + timedelta(days=3), time(11, 0))
        )
        hora_alt = HoraMedica.objects.create(
            bloque=bloque_alt, inicio=inicio_alt, fin=inicio_alt + timedelta(minutes=30)
        )
        services.suspender_agenda(self.agenda, actor=self.user, motivo="Ausencia ficticia")
        propuesta = PropuestaReagendamiento.objects.get(
            estado=PropuestaReagendamiento.Estado.PENDIENTE
        )
        hora_alt.estado = HoraMedica.Estado.CANCELADA
        hora_alt.save(update_fields=["estado"])

        with self.assertRaises(services.ErrorMotor):
            services.aprobar_propuesta(propuesta.pk, actor=self.user, motivo="Intento fallido")
        propuesta.refresh_from_db()
        cita.refresh_from_db()
        self.assertEqual(propuesta.estado, PropuestaReagendamiento.Estado.FALLIDA)
        self.assertEqual(cita.estado, Cita.Estado.REAGENDAMIENTO_PENDIENTE)
        self.assertTrue(Alerta.objects.filter(tipo="PROPUESTA_FALLIDA").exists())

    def test_suspension_cancela_ofertas_pendientes(self):
        oferta = services.ofrecer_hora(self.hora.pk, actor=self.user)
        services.suspender_agenda(self.agenda, actor=self.user, motivo="Suspensión demo")
        oferta.refresh_from_db()
        self.s1.refresh_from_db()
        self.assertEqual(oferta.estado, OfertaHora.Estado.CANCELADA)
        self.assertEqual(self.s1.estado, Solicitud.Estado.EN_LISTA_ESPERA)


class PermissionTests(BaseEngineTest):
    def setUp(self):
        super().setUp()
        self.user_p1 = User.objects.create_user(username="pac1", password="Demo12345!")
        self.user_p2 = User.objects.create_user(username="pac2", password="Demo12345!")
        self.p1.user = self.user_p1
        self.p1.save(update_fields=["user"])
        self.p2.user = self.user_p2
        self.p2.save(update_fields=["user"])
        PerfilUsuario.objects.create(user=self.user_p1, rol=PerfilUsuario.Rol.PACIENTE, establecimiento=self.est)
        PerfilUsuario.objects.create(user=self.user_p2, rol=PerfilUsuario.Rol.PACIENTE, establecimiento=self.est)
        self.staff2 = User.objects.create_user(username="staff2", password="Demo12345!")
        PerfilUsuario.objects.create(
            user=self.staff2, rol=PerfilUsuario.Rol.ADMISION, establecimiento=self.est2
        )
        self.staff1 = User.objects.create_user(username="staff1", password="Demo12345!")
        PerfilUsuario.objects.create(
            user=self.staff1, rol=PerfilUsuario.Rol.ADMISION, establecimiento=self.est
        )

    def test_paciente_no_accede_al_panel(self):
        c = Client()
        self.assertTrue(c.login(username="pac1", password="Demo12345!"))
        self.assertEqual(c.get(reverse("pacientes_lista")).status_code, 403)
        self.assertEqual(c.get(reverse("dashboard")).status_code, 403)

    def test_paciente_no_accede_a_bandeja_whatsapp(self):
        c = Client()
        self.assertTrue(c.login(username="pac1", password="Demo12345!"))
        self.assertEqual(c.get(reverse("notificaciones_lista")).status_code, 403)

    def test_admision_accede_a_bandeja_whatsapp(self):
        c = Client()
        self.assertTrue(c.login(username="staff1", password="Demo12345!"))
        self.assertEqual(c.get(reverse("notificaciones_lista")).status_code, 200)

    def test_bandeja_whatsapp_respeta_establecimiento(self):
        mensaje, _ = encolar_mensaje(
            dedupe_key="prueba:whatsapp:establecimiento",
            destinatario_tipo="PACIENTE",
            destinatario_id=self.p1.uuid,
            destinatario_nombre=self.p1.nombre_completo,
            destinatario_contacto=self.p1.telefono,
            canal="WHATSAPP",
            asunto="Prueba de alcance",
            cuerpo="Solo debe verlo el establecimiento de la paciente.",
        )
        c = Client()
        self.assertTrue(c.login(username="staff2", password="Demo12345!"))
        respuesta = c.get(reverse("notificaciones_lista"))
        self.assertNotContains(respuesta, "Prueba de alcance")
        self.assertEqual(
            c.post(reverse("notificacion_enviada_manual", args=[mensaje.pk])).status_code,
            404,
        )
        c.post(reverse("notificaciones_despachar"))
        mensaje.refresh_from_db()
        self.assertEqual(mensaje.estado, MensajeNotificacion.Estado.PENDIENTE)
        c.logout()
        self.assertTrue(c.login(username="staff1", password="Demo12345!"))
        respuesta = c.get(reverse("notificaciones_lista"))
        self.assertContains(respuesta, "Prueba de alcance")
        c.post(reverse("notificaciones_despachar"))
        mensaje.refresh_from_db()
        self.assertEqual(mensaje.estado, MensajeNotificacion.Estado.SIMULADO)

    def test_paciente_no_ve_oferta_de_otro(self):
        oferta = services.ofrecer_hora(self.hora.pk, actor=self.user)
        self.assertEqual(oferta.solicitud.paciente, self.p1)
        c = Client()
        self.assertTrue(c.login(username="pac2", password="Demo12345!"))
        respuesta = c.post(reverse("portal_oferta_aceptar", args=[oferta.pk]))
        self.assertEqual(respuesta.status_code, 404)
        oferta.refresh_from_db()
        self.assertEqual(oferta.estado, OfertaHora.Estado.PENDIENTE)

    def test_funcionario_de_otro_establecimiento_no_ve_paciente(self):
        c = Client()
        self.assertTrue(c.login(username="staff2", password="Demo12345!"))
        self.assertEqual(c.get(reverse("paciente_detalle", args=[self.p1.pk])).status_code, 403)

    def test_hospital_ve_paciente_con_cita_en_su_agenda(self):
        paciente = self._paciente("P3", "Carla", "Tres")
        paciente.establecimiento_referencia = self.est2
        paciente.save(update_fields=["establecimiento_referencia"])
        solicitud = Solicitud.objects.create(
            paciente=paciente,
            especialidad=self.esp,
            establecimiento_origen=self.est2,
            establecimiento_destino=None,
            estado=Solicitud.Estado.AGENDADA,
            fecha_ingreso=self.hoy,
        )
        Cita.objects.create(solicitud=solicitud, hora=self.hora2)

        c = Client()
        self.assertTrue(c.login(username="staff1", password="Demo12345!"))
        self.assertEqual(
            c.get(reverse("paciente_detalle", args=[paciente.pk])).status_code, 200
        )
        self.assertEqual(
            c.get(reverse("solicitud_detalle", args=[solicitud.uuid])).status_code,
            200,
        )

    def test_funcionario_de_otro_establecimiento_no_ve_solicitud(self):
        c = Client()
        self.assertTrue(c.login(username="staff2", password="Demo12345!"))
        self.assertEqual(
            c.get(reverse("solicitud_detalle", args=[self.s1.uuid])).status_code, 403
        )

    def test_funcionario_del_mismo_establecimiento_accede(self):
        c = Client()
        self.assertTrue(c.login(username="staff1", password="Demo12345!"))
        self.assertEqual(c.get(reverse("pacientes_lista")).status_code, 200)
        self.assertEqual(c.get(reverse("solicitud_detalle", args=[self.s1.uuid])).status_code, 200)

    def test_admision_no_gestiona_agendas(self):
        c = Client()
        self.assertTrue(c.login(username="staff1", password="Demo12345!"))
        self.assertEqual(c.get(reverse("agenda_nueva")).status_code, 403)

    def test_formulario_solicitud_filtra_pacientes_por_establecimiento(self):
        ajeno = self._paciente("P3", "Paciente", "Ajeno")
        ajeno.establecimiento_referencia = self.est2
        ajeno.save(update_fields=["establecimiento_referencia"])
        form = SolicitudForm(user=self.staff1)
        self.assertNotIn(ajeno, form.fields["paciente"].queryset)
        self.assertIn(self.p1, form.fields["paciente"].queryset)
