"""Management command to send appointment reminders.

Runs daily at 12:00 PM — sends reminders for TOMORROW's appointments.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.appointments.models import Appointment, AppointmentStatus
from apps.notifications.models import NotificationConfig, NotificationLog
from apps.notifications.services import send_reminder


class Command(BaseCommand):
    help = "Envía recordatorios a las 9:00 del día previo al turno"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simular envío sin enviar",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Reenviar incluso si ya fue enviado",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        force = options["force"]

        tomorrow = timezone.localdate() + timedelta(days=1)

        candidates = Appointment.objects.filter(
            date=tomorrow,
            send_reminder=True,
            status__in=[AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED],
        ).select_related("resource", "professional")

        stats = {
            "sent": 0,
            "no_config": 0,
            "dedup": 0,
            "error": 0,
        }

        for appt in candidates:
            # ── 1. NotificationConfig check ────────────────────────────────
            try:
                config = NotificationConfig.objects.get(resource=appt.resource)
            except NotificationConfig.DoesNotExist:
                stats["no_config"] += 1
                continue

            if not config.reminder_enabled:
                stats["no_config"] += 1
                continue

            # ── 2. Dedup check ─────────────────────────────────────────────
            if not force:
                already_sent = NotificationLog.objects.filter(
                    appointment=appt,
                    notification_type=NotificationLog.Type.REMINDER,
                    channel=NotificationLog.Channel.EMAIL,
                    status=NotificationLog.Status.SENT,
                ).exists()
                if already_sent:
                    stats["dedup"] += 1
                    continue

            # ── 3. Dry-run / Send ─────────────────────────────────────────
            if dry_run:
                self.stdout.write(
                    f"[DRY-RUN] Enviaría recordatorio a {appt.patient_name} "
                    f"({appt.date} {appt.start_time})"
                )
                stats["sent"] += 1
                continue

            try:
                log = send_reminder(appt)
                if log.status == NotificationLog.Status.SENT:
                    stats["sent"] += 1
                else:
                    stats["error"] += 1
                self.stdout.write(
                    f"  {appt.patient_name} — {log.get_status_display()}"
                )
            except Exception as e:
                stats["error"] += 1
                self.stderr.write(
                    f"  ERROR: {appt.patient_name} (#{appt.pk}): {e}"
                )

        # ── Summary ───────────────────────────────────────────────────────
        total_skipped = stats["no_config"] + stats["dedup"]

        if dry_run:
            summary = (
                f"[DRY-RUN] {stats['sent']} recordatorios listos para enviar, "
                f"{total_skipped} omitidos, {stats['error']} errores"
            )
        else:
            summary = (
                f"{stats['sent']} recordatorios enviados, "
                f"{total_skipped} omitidos, {stats['error']} errores"
            )
        self.stdout.write(self.style.SUCCESS(summary))
