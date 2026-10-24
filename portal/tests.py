from __future__ import annotations

from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import PerfilUsuario
from gestion.models import (
    Agenda,
    BloqueAgenda,
    Cita,
    Especialidad,
    Establecimiento,
    HoraMedica,
    OfertaHora,
    Paciente,
    Profesional,
    Solicitud,
)

User = get_user_model()


class PortalSolicitudTests(TestCase):
    def setUp(self):
        self.hoy = timezone.localdate()
        self.est = Establecimiento.objects.create(codigo="EST-PORTAL", nombre="CESFAM Demo")
        self.esp = Especialidad.objects.create(codigo="ESP-PORTAL", nombre="Cardiología Demo")
        self.prof = Profesional.objects.create(
            nombres="Ana",
            apellidos="Demo",
            documento="PROF-PORTAL",
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
        inicio = timezone.make_aware(
            datetime.combine(self.hoy + timedelta(days=1), time(9, 0))
        )
        self.hora = HoraMedica.objects.create(
            bloque=self.bloque,
            inicio=inicio,
            fin=inicio + timedelta(minutes=30),
        )
        self.user = User.objects.create_user(
            username="paciente@demo.cl", password="Demo12345!"
        )
        PerfilUsuario.objects.create(
            user=self.user,
            rol=PerfilUsuario.Rol.PACIENTE,
            establecimiento=self.est,
        )
        self.paciente = Paciente.objects.create(
            tipo_documento=Paciente.TipoDocumento.RUT,
            numero_documento="11111111-1",
            nombres="Elena",
            apellidos="Demo Rojas",
            fecha_nacimiento=self.hoy - timedelta(days=35 * 365),
            telefono="+56 9 1111 1111",
            email="paciente@demo.cl",
            canal_preferido=Paciente.CanalPreferido.PORTAL,
            establecimiento_referencia=self.est,
            user=self.user,
        )
        self.client.force_login(self.user)

    def test_formulario_solicitar_hora_disponible(self):
        respuesta = self.client.get(reverse("portal_solicitud_nueva"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Solicitar hora")

    def test_paciente_solicita_especialidad_y_recibe_oferta(self):
        respuesta = self.client.post(
            reverse("portal_solicitud_nueva"),
            {"especialidad": self.esp.pk, "observaciones": "Prefiero horario de mañana."},
        )
        self.assertRedirects(respuesta, reverse("portal_ofertas"))

        solicitud = Solicitud.objects.get()
        self.assertEqual(solicitud.paciente, self.paciente)
        self.assertEqual(solicitud.especialidad, self.esp)
        self.assertEqual(solicitud.origen, Solicitud.Origen.PORTAL)
        self.assertEqual(solicitud.estado, Solicitud.Estado.OFERTA_PENDIENTE)

        oferta = OfertaHora.objects.get()
        self.assertEqual(oferta.solicitud, solicitud)
        self.assertEqual(oferta.hora, self.hora)
        self.assertEqual(oferta.estado, OfertaHora.Estado.PENDIENTE)

        respuesta = self.client.post(reverse("portal_oferta_aceptar", args=[oferta.pk]))
        self.assertRedirects(respuesta, reverse("portal_horas"))
        self.assertEqual(Cita.objects.count(), 1)

    def test_sin_disponibilidad_queda_en_lista_de_espera(self):
        self.hora.estado = HoraMedica.Estado.BLOQUEADA
        self.hora.save(update_fields=["estado"])

        respuesta = self.client.post(
            reverse("portal_solicitud_nueva"),
            {"especialidad": self.esp.pk, "observaciones": ""},
        )
        solicitud = Solicitud.objects.get()
        self.assertRedirects(
            respuesta,
            reverse("portal_solicitud_detalle", args=[solicitud.uuid]),
        )
        self.assertEqual(solicitud.estado, Solicitud.Estado.EN_LISTA_ESPERA)
        self.assertFalse(OfertaHora.objects.exists())

    def test_no_permite_duplicar_solicitud_activa(self):
        datos = {"especialidad": self.esp.pk, "observaciones": ""}
        self.client.post(reverse("portal_solicitud_nueva"), datos)
        respuesta = self.client.post(reverse("portal_solicitud_nueva"), datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Ya tienes una solicitud activa")
        self.assertEqual(Solicitud.objects.count(), 1)
