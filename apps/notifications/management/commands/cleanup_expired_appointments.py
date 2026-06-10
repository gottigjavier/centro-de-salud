"""Management command to soft-delete expired (non-active) appointments."""
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.appointments.models import Appointment, AppointmentStatus


class Command(BaseCommand):
    help = (
        "Elimina (soft-delete) turnos expirados no finalizados. "
        "Idempotente: los turnos ya eliminados no se procesan de nuevo."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mostrar qué se eliminaría sin hacerlo",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        today = timezone.localdate()

        # Idempotente: el default manager (AppointmentManager) ya filtra
        # deleted_at__isnull=True, así que los ya eliminados no aparecen.
        expired = Appointment.objects.filter(
            date__lt=today,
        ).exclude(
            status__in=[AppointmentStatus.IN_PROGRESS, AppointmentStatus.COMPLETED],
        )

        count = expired.count()

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: {count} turnos expirados serían eliminados"
                )
            )
            for appt in expired[:20]:
                self.stdout.write(
                    f"  - Turno #{appt.id}: {appt.date} {appt.patient_name} "
                    f"({appt.get_status_display()})"
                )
            if count > 20:
                self.stdout.write(f"  ... y {count - 20} más")
        else:
            updated = expired.update(deleted_at=timezone.now())
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ {updated} turnos expirados eliminados"
                )
            )
