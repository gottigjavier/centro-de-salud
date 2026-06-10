from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Envía recordatorios de turnos próximos (stub — pendiente de implementación)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simular envío sin enviar",
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS("send_reminders: no implementado (stub)")
        )
