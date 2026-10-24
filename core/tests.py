from urllib.parse import unquote

from django.test import SimpleTestCase

from core.models import MensajeNotificacion
from core.whatsapp import generar_enlace_whatsapp, normalizar_telefono


class WhatsAppHelpersTests(SimpleTestCase):
    def test_normaliza_telefono_con_espacios_y_signos(self):
        self.assertEqual(normalizar_telefono("+56 9 1111 1111"), "56911111111")
        self.assertEqual(normalizar_telefono("0056 9 1111 1111"), "56911111111")
        self.assertEqual(normalizar_telefono(""), "")

    def test_enlace_incluye_texto_codificado(self):
        enlace = generar_enlace_whatsapp(
            "+56 9 1111 1111", "Hola Elena\n\nTu hora está confirmada."
        )
        self.assertTrue(enlace.startswith("https://wa.me/56911111111?text="))
        self.assertIn("Hola Elena", unquote(enlace))
        self.assertIn("Tu hora está confirmada.", unquote(enlace))

    def test_mensaje_whatsapp_expone_enlace_y_portal_no(self):
        whatsapp = MensajeNotificacion(
            canal=MensajeNotificacion.Canal.WHATSAPP,
            destinatario_contacto="+56 9 1111 1111",
            asunto="Hora confirmada",
            cuerpo="Tu hora quedó confirmada.",
        )
        self.assertTrue(whatsapp.enlace_whatsapp.startswith("https://wa.me/"))

        portal = MensajeNotificacion(
            canal=MensajeNotificacion.Canal.PORTAL,
            destinatario_contacto="Portal del paciente",
            asunto="Hora confirmada",
            cuerpo="Tu hora quedó confirmada.",
        )
        self.assertEqual(portal.enlace_whatsapp, "")
