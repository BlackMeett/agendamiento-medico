from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from core.notifications import despachar_pendientes


class Command(BaseCommand):
    help = "Despacha los mensajes pendientes del outbox (WhatsApp, correo y SMS)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limite",
            type=int,
            default=100,
            help="Máximo de mensajes a procesar en esta ejecución (por defecto: 100).",
        )

    def handle(self, *args, **options):
        limite = options["limite"]
        if limite < 1:
            raise CommandError("--limite debe ser mayor que cero.")

        resultado = despachar_pendientes(limite=limite)
        self.stdout.write(
            "Despacho: "
            f"{resultado['procesados']} procesados, "
            f"{resultado['fallidos']} con error, "
            f"{resultado['pendientes']} pendientes."
        )
