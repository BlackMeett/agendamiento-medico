from __future__ import annotations

from django.core.management.base import BaseCommand

from core.notifications import despachar_pendientes
from gestion.services import crear_recordatorios_proximos


class Command(BaseCommand):
    help = "Crea recordatorios de 24 h para citas confirmadas y despacha el outbox."

    def add_arguments(self, parser):
        parser.add_argument(
            "--ventana-horas",
            type=int,
            default=24,
            help="Ventana de anticipación en horas (por defecto: 24).",
        )
        parser.add_argument(
            "--sin-despacho",
            action="store_true",
            help="Solo encola los recordatorios, sin procesar canales externos.",
        )

    def handle(self, *args, **options):
        creados = crear_recordatorios_proximos(ventana_horas=options["ventana_horas"])
        self.stdout.write(f"Recordatorios nuevos: {creados}")
        if options["sin_despacho"]:
            return
        resultado = despachar_pendientes()
        self.stdout.write(
            "Despacho: "
            f"{resultado['procesados']} procesados, "
            f"{resultado['fallidos']} con error, "
            f"{resultado['pendientes']} pendientes."
        )
