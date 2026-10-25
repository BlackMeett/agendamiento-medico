from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from core.notifications import despachar_pendientes
from gestion.services import (
    asignar_ofertas_disponibles,
    crear_recordatorios_proximos,
    procesar_eventos_pendientes,
    vencer_ofertas,
)


class Command(BaseCommand):
    help = (
        "Ejecuta el motor de agendamiento (eventos, vencimientos, ofertas y "
        "recordatorios) y despacha las notificaciones pendientes."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--limite",
            type=int,
            default=25,
            help="Máximo de solicitudes en espera a evaluar (por defecto: 25).",
        )
        parser.add_argument(
            "--sin-despacho",
            action="store_true",
            help="Ejecuta el motor sin procesar los canales de notificación.",
        )

    def handle(self, *args, **options):
        limite = options["limite"]
        if limite < 1:
            raise CommandError("--limite debe ser mayor que cero.")

        eventos = procesar_eventos_pendientes()
        vencidas = vencer_ofertas()
        ofertas = asignar_ofertas_disponibles(limite=limite)
        recordatorios = crear_recordatorios_proximos()
        self.stdout.write(
            "Motor: "
            f"{eventos['procesados']} eventos, "
            f"{eventos['fallidos']} fallidos, "
            f"{vencidas} ofertas vencidas, "
            f"{ofertas} ofertas nuevas, "
            f"{recordatorios} recordatorios."
        )

        if options["sin_despacho"]:
            return

        resultado = despachar_pendientes()
        self.stdout.write(
            "Despacho: "
            f"{resultado['procesados']} procesados, "
            f"{resultado['fallidos']} con error, "
            f"{resultado['pendientes']} pendientes."
        )
