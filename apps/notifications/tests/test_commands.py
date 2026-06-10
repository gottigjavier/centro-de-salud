"""Tests for management commands — send_reminders and cleanup_expired_appointments."""
from datetime import time, timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.appointments.models import Appointment, AppointmentStatus
from apps.notifications.models import NotificationConfig, NotificationLog
from apps.professionals.models import Professional
from apps.resources.models import Resource


class SendRemindersCommandTest(TestCase):
    """Tests for the send_reminders management command.

    El comando se ejecuta diario a las 12:00 PM y envía recordatorios
    para turnos del DÍA SIGUIENTE (date == tomorrow).
    """

    @classmethod
    def setUpTestData(cls):
        cls.tomorrow = timezone.localdate() + timedelta(days=1)
        cls.professional = Professional.objects.create(
            first_name="Test", last_name="Prof",
            specialty="general", license_number="MAT-REM1",
        )
        cls.professional2 = Professional.objects.create(
            first_name="Otro", last_name="Prof",
            specialty="general", license_number="MAT-REM2",
        )
        cls.resource = Resource.objects.create(name="Consultorio REM", type="office")
        cls.resource_no_config = Resource.objects.create(name="Sin Config", type="office")
        cls.resource_disabled = Resource.objects.create(
            name="Recordatorio Desactivado", type="office",
        )
        cls.resource2 = Resource.objects.create(name="Consultorio REM2", type="office")

        # NotificationConfigs
        NotificationConfig.objects.create(
            resource=cls.resource,
            reminder_enabled=True,
        )
        NotificationConfig.objects.create(
            resource=cls.resource_disabled,
            reminder_enabled=False,
        )
        NotificationConfig.objects.create(
            resource=cls.resource2,
            reminder_enabled=True,
        )

        # ── Appointments (all for tomorrow) ──────────────────────────────
        # Normal: qualifies
        cls.appt_normal = Appointment.objects.create(
            resource=cls.resource,
            professional=cls.professional,
            patient_name="Normal",
            patient_dni="11111111",
            patient_phone="5555-1111",
            patient_email="normal@test.com",
            date=cls.tomorrow,
            start_time=time(10, 0),
            end_time=time(10, 30),
            status=AppointmentStatus.SCHEDULED,
            send_reminder=True,
        )

        # No config: resource without NotificationConfig
        cls.appt_no_config = Appointment.objects.create(
            resource=cls.resource_no_config,
            professional=cls.professional,
            patient_name="Sin Config",
            patient_dni="22222222",
            patient_phone="5555-2222",
            patient_email="noconfig@test.com",
            date=cls.tomorrow,
            start_time=time(10, 0),
            end_time=time(10, 30),
            status=AppointmentStatus.SCHEDULED,
            send_reminder=True,
        )

        # Disabled config: reminder_enabled=False
        cls.appt_disabled = Appointment.objects.create(
            resource=cls.resource_disabled,
            professional=cls.professional,
            patient_name="Desactivado",
            patient_dni="33333333",
            patient_phone="5555-3333",
            patient_email="disabled@test.com",
            date=cls.tomorrow,
            start_time=time(10, 0),
            end_time=time(10, 30),
            status=AppointmentStatus.SCHEDULED,
            send_reminder=True,
        )

        # send_reminder=False (tomorrow but opt-out)
        cls.appt_no_reminder = Appointment.objects.create(
            resource=cls.resource2,
            professional=cls.professional2,
            patient_name="Sin Recordatorio",
            patient_dni="66666666",
            patient_phone="5555-6666",
            patient_email="noreminder@test.com",
            date=cls.tomorrow,
            start_time=time(11, 0),
            end_time=time(11, 30),
            status=AppointmentStatus.SCHEDULED,
            send_reminder=False,
        )

        # Status filter: ARRIVED (not SCHEDULED/CONFIRMED)
        cls.appt_arrived = Appointment.objects.create(
            resource=cls.resource2,
            professional=cls.professional2,
            patient_name="Arrived",
            patient_dni="77777777",
            patient_phone="5555-7777",
            patient_email="arrived@test.com",
            date=cls.tomorrow,
            start_time=time(12, 0),
            end_time=time(12, 30),
            status=AppointmentStatus.ARRIVED,
            send_reminder=True,
        )

        # Same patient, 2 appointments for tomorrow
        cls.appt_same_patient_1 = Appointment.objects.create(
            resource=cls.resource2,
            professional=cls.professional2,
            patient_name="Mismo Paciente",
            patient_dni="88888888",
            patient_phone="5555-8888",
            patient_email="same@test.com",
            date=cls.tomorrow,
            start_time=time(13, 0),
            end_time=time(13, 30),
            status=AppointmentStatus.CONFIRMED,
            send_reminder=True,
        )
        cls.appt_same_patient_2 = Appointment.objects.create(
            resource=cls.resource2,
            professional=cls.professional2,
            patient_name="Mismo Paciente",
            patient_dni="88888888",
            patient_phone="5555-8888",
            patient_email="same@test.com",
            date=cls.tomorrow,
            start_time=time(14, 0),
            end_time=time(14, 30),
            status=AppointmentStatus.CONFIRMED,
            send_reminder=True,
        )

        # Not tomorrow: should be excluded by query
        cls.appt_today = Appointment.objects.create(
            resource=cls.resource,
            professional=cls.professional,
            patient_name="Hoy",
            patient_dni="99999999",
            patient_phone="5555-9999",
            patient_email="today@test.com",
            date=timezone.localdate(),
            start_time=time(10, 0),
            end_time=time(10, 30),
            status=AppointmentStatus.SCHEDULED,
            send_reminder=True,
        )
        cls.appt_yesterday = Appointment.objects.create(
            resource=cls.resource,
            professional=cls.professional,
            patient_name="Ayer",
            patient_dni="10101010",
            patient_phone="5555-1010",
            patient_email="yesterday@test.com",
            date=timezone.localdate() - timedelta(days=1),
            start_time=time(10, 0),
            end_time=time(10, 30),
            status=AppointmentStatus.SCHEDULED,
            send_reminder=True,
        )

    def setUp(self):
        """Clean NotificationLog before each test."""
        NotificationLog.objects.all().delete()

    # ── Normal execution ─────────────────────────────────────────────────

    @patch("apps.notifications.management.commands.send_reminders.send_reminder")
    def test_normal_execution_sends_reminders(self, mock_send):
        """Appointments for tomorrow matching criteria → send_reminder() called."""
        mock_send.return_value = NotificationLog(
            status=NotificationLog.Status.SENT,
            notification_type=NotificationLog.Type.REMINDER,
        )

        out = StringIO()
        call_command("send_reminders", stdout=out)

        # Qualifying: appt_normal + same_patient_1 + same_patient_2 = 3
        # Excluded: no_config (no config), disabled (config disabled),
        #   no_reminder (send_reminder=False), arrived (status),
        #   today/yesterday (not tomorrow)
        self.assertEqual(mock_send.call_count, 3)
        output = out.getvalue()
        self.assertIn("3 recordatorios enviados", output)

    # ── Dry run ──────────────────────────────────────────────────────────

    @patch("apps.notifications.management.commands.send_reminders.send_reminder")
    def test_dry_run_lists_candidates_without_sending(self, mock_send):
        """--dry-run → lists candidates, no emails sent, no logs created."""
        out = StringIO()
        call_command("send_reminders", dry_run=True, stdout=out)

        mock_send.assert_not_called()
        output = out.getvalue()
        self.assertIn("[DRY-RUN]", output)
        self.assertIn("Normal", output)
        self.assertIn("recordatorios listos para enviar", output)

    # ── Dedup ────────────────────────────────────────────────────────────

    @patch("apps.notifications.management.commands.send_reminders.send_reminder")
    def test_dedup_skips_already_sent(self, mock_send):
        """Appointment with existing REMINDER+SENT → skipped."""
        mock_send.return_value = NotificationLog(
            status=NotificationLog.Status.SENT,
            notification_type=NotificationLog.Type.REMINDER,
        )

        NotificationLog.objects.create(
            appointment=self.appt_normal,
            channel=NotificationLog.Channel.EMAIL,
            notification_type=NotificationLog.Type.REMINDER,
            recipient="normal@test.com",
            status=NotificationLog.Status.SENT,
            sent_at=timezone.now(),
        )

        out = StringIO()
        call_command("send_reminders", stdout=out)

        # Only the 2 same_patient appointments should be sent
        # appt_normal is dedup-skipped
        self.assertEqual(mock_send.call_count, 2)
        output = out.getvalue()
        self.assertIn("omitidos", output)

    @patch("apps.notifications.management.commands.send_reminders.send_reminder")
    def test_force_resends_despite_existing_log(self, mock_send):
        """--force → resends even if REMINDER+SENT log exists."""
        mock_send.return_value = NotificationLog(
            status=NotificationLog.Status.SENT,
            notification_type=NotificationLog.Type.REMINDER,
        )

        NotificationLog.objects.create(
            appointment=self.appt_normal,
            channel=NotificationLog.Channel.EMAIL,
            notification_type=NotificationLog.Type.REMINDER,
            recipient="normal@test.com",
            status=NotificationLog.Status.SENT,
            sent_at=timezone.now(),
        )

        out = StringIO()
        call_command("send_reminders", force=True, stdout=out)

        # All 3 qualifying sent (no dedup with --force)
        self.assertEqual(mock_send.call_count, 3)
        output = out.getvalue()
        self.assertIn("3 recordatorios enviados", output)

    # ── Config checks ────────────────────────────────────────────────────

    @patch("apps.notifications.management.commands.send_reminders.send_reminder")
    def test_skips_without_notification_config(self, mock_send):
        """Resource sin NotificationConfig → skip."""
        mock_send.return_value = NotificationLog(
            status=NotificationLog.Status.SENT,
            notification_type=NotificationLog.Type.REMINDER,
        )

        out = StringIO()
        call_command("send_reminders", stdout=out)

        # Only appt_normal + 2 same_patient = 3 calls
        self.assertEqual(mock_send.call_count, 3)

    @patch("apps.notifications.management.commands.send_reminders.send_reminder")
    def test_skips_notification_config_disabled(self, mock_send):
        """Config con reminder_enabled=False → skip."""
        mock_send.return_value = NotificationLog(
            status=NotificationLog.Status.SENT,
            notification_type=NotificationLog.Type.REMINDER,
        )

        out = StringIO()
        call_command("send_reminders", stdout=out)

        # Only appt_normal + 2 same_patient = 3 calls
        self.assertEqual(mock_send.call_count, 3)

    # ── Query filters ────────────────────────────────────────────────────

    @patch("apps.notifications.management.commands.send_reminders.send_reminder")
    def test_filters_by_tomorrow_only(self, mock_send):
        """Solo turnos con date=tomorrow son considerados."""
        mock_send.return_value = NotificationLog(
            status=NotificationLog.Status.SENT,
            notification_type=NotificationLog.Type.REMINDER,
        )

        out = StringIO()
        call_command("send_reminders", stdout=out)

        # Today's and yesterday's appointments are excluded by query
        self.assertEqual(mock_send.call_count, 3)

    @patch("apps.notifications.management.commands.send_reminders.send_reminder")
    def test_send_reminder_false_excluded(self, mock_send):
        """send_reminder=False → excluido."""
        mock_send.return_value = NotificationLog(
            status=NotificationLog.Status.SENT,
            notification_type=NotificationLog.Type.REMINDER,
        )

        out = StringIO()
        call_command("send_reminders", stdout=out)

        # no_reminder has send_reminder=False → excluded
        self.assertEqual(mock_send.call_count, 3)

    @patch("apps.notifications.management.commands.send_reminders.send_reminder")
    def test_status_filter_excludes_non_candidates(self, mock_send):
        """Status ARRIVED, IN_PROGRESS, COMPLETED, CANCELLED → excluidos."""
        mock_send.return_value = NotificationLog(
            status=NotificationLog.Status.SENT,
            notification_type=NotificationLog.Type.REMINDER,
        )

        out = StringIO()
        call_command("send_reminders", stdout=out)

        # appt_arrived has ARRIVED status → excluded
        self.assertEqual(mock_send.call_count, 3)

    # ── Multiple appointments same patient ────────────────────────────────

    @patch("apps.notifications.management.commands.send_reminders.send_reminder")
    def test_multiple_appointments_same_patient(self, mock_send):
        """Mismo paciente con 2 turnos → cada uno recibe su recordatorio."""
        mock_send.return_value = NotificationLog(
            status=NotificationLog.Status.SENT,
            notification_type=NotificationLog.Type.REMINDER,
        )

        out = StringIO()
        call_command("send_reminders", stdout=out)

        # appt_normal + same_patient_1 + same_patient_2 = 3
        self.assertEqual(mock_send.call_count, 3)

    # ── Output format ────────────────────────────────────────────────────

    @patch("apps.notifications.management.commands.send_reminders.send_reminder")
    def test_output_format_with_counts(self, mock_send):
        """Output termina con 'X enviados, Y omitidos, Z errores'."""
        mock_send.return_value = NotificationLog(
            status=NotificationLog.Status.SENT,
            notification_type=NotificationLog.Type.REMINDER,
        )

        out = StringIO()
        call_command("send_reminders", stdout=out)
        output = out.getvalue().strip()

        # 3 enviados, 2 omitidos (no_config + disabled)
        self.assertRegex(output, r"\d+ recordatorios enviados, \d+ omitidos, \d+ errores")


class CleanupExpiredCommandTest(TestCase):
    """Tests for the cleanup_expired_appointments management command."""

    @classmethod
    def setUpTestData(cls):
        cls.today = timezone.localdate()
        cls.yesterday = cls.today - timedelta(days=1)
        cls.tomorrow = cls.today + timedelta(days=1)
        cls.professional = Professional.objects.create(
            first_name="Cleanup", last_name="Test",
            specialty="general", license_number="MAT-CLN",
        )
        cls.resource = Resource.objects.create(name="Cleanup Resource", type="office")

        # Yesterday — should be soft-deleted
        cls.appt_expired_scheduled = Appointment.objects.create(
            resource=cls.resource,
            professional=cls.professional,
            patient_name="Expired Scheduled",
            patient_dni="11111111",
            patient_phone="5555-0001",
            date=cls.yesterday,
            start_time=time(9, 0),
            end_time=time(9, 30),
            status=AppointmentStatus.SCHEDULED,
        )
        cls.appt_expired_confirmed = Appointment.objects.create(
            resource=cls.resource,
            professional=cls.professional,
            patient_name="Expired Confirmed",
            patient_dni="22222222",
            patient_phone="5555-0002",
            date=cls.yesterday,
            start_time=time(10, 0),
            end_time=time(10, 30),
            status=AppointmentStatus.CONFIRMED,
        )
        cls.appt_expired_cancelled = Appointment.objects.create(
            resource=cls.resource,
            professional=cls.professional,
            patient_name="Expired Cancelled",
            patient_dni="33333333",
            patient_phone="5555-0003",
            date=cls.yesterday,
            start_time=time(11, 0),
            end_time=time(11, 30),
            status=AppointmentStatus.CANCELLED,
        )
        cls.appt_expired_no_show = Appointment.objects.create(
            resource=cls.resource,
            professional=cls.professional,
            patient_name="Expired No Show",
            patient_dni="44444444",
            patient_phone="5555-0004",
            date=cls.yesterday,
            start_time=time(12, 0),
            end_time=time(12, 30),
            status=AppointmentStatus.NO_SHOW,
        )
        cls.appt_expired_arrived = Appointment.objects.create(
            resource=cls.resource,
            professional=cls.professional,
            patient_name="Expired Arrived",
            patient_dni="55555555",
            patient_phone="5555-0005",
            date=cls.yesterday,
            start_time=time(13, 0),
            end_time=time(13, 30),
            status=AppointmentStatus.ARRIVED,
        )

        # Yesterday but IN_PROGRESS / COMPLETED — should NOT be deleted
        cls.appt_in_progress = Appointment.objects.create(
            resource=cls.resource,
            professional=cls.professional,
            patient_name="In Progress",
            patient_dni="66666666",
            patient_phone="5555-0006",
            date=cls.yesterday,
            start_time=time(14, 0),
            end_time=time(14, 30),
            status=AppointmentStatus.IN_PROGRESS,
        )
        cls.appt_completed = Appointment.objects.create(
            resource=cls.resource,
            professional=cls.professional,
            patient_name="Completed",
            patient_dni="77777777",
            patient_phone="5555-0007",
            date=cls.yesterday,
            start_time=time(15, 0),
            end_time=time(15, 30),
            status=AppointmentStatus.COMPLETED,
        )

        # Today / Future — should NOT be deleted
        cls.appt_today = Appointment.objects.create(
            resource=cls.resource,
            professional=cls.professional,
            patient_name="Today",
            patient_dni="88888888",
            patient_phone="5555-0008",
            date=cls.today,
            start_time=time(9, 0),
            end_time=time(9, 30),
            status=AppointmentStatus.SCHEDULED,
        )
        cls.appt_future = Appointment.objects.create(
            resource=cls.resource,
            professional=cls.professional,
            patient_name="Future",
            patient_dni="99999999",
            patient_phone="5555-0009",
            date=cls.tomorrow,
            start_time=time(9, 0),
            end_time=time(9, 30),
            status=AppointmentStatus.SCHEDULED,
        )

    def setUp(self):
        """Reset soft-deletes before each test."""
        Appointment.all_objects.all().update(deleted_at=None)

    # ── Normal execution ─────────────────────────────────────────────────

    def test_cleanup_soft_deletes_expired(self):
        """Turnos expirados (yesterday) con status no-activo → soft-delete."""
        out = StringIO()
        call_command("cleanup_expired_appointments", stdout=out)

        # 5 expired non-active should be deleted
        self.assertIsNotNone(
            Appointment.all_objects.get(pk=self.appt_expired_scheduled.pk).deleted_at,
        )
        self.assertIsNotNone(
            Appointment.all_objects.get(pk=self.appt_expired_confirmed.pk).deleted_at,
        )
        self.assertIsNotNone(
            Appointment.all_objects.get(pk=self.appt_expired_cancelled.pk).deleted_at,
        )
        self.assertIsNotNone(
            Appointment.all_objects.get(pk=self.appt_expired_no_show.pk).deleted_at,
        )
        self.assertIsNotNone(
            Appointment.all_objects.get(pk=self.appt_expired_arrived.pk).deleted_at,
        )

        # Count in output
        output = out.getvalue()
        self.assertIn("turnos expirados eliminados", output)

    # ── Preserve active statuses ─────────────────────────────────────────

    def test_preserves_in_progress(self):
        """IN_PROGRESS → no se elimina."""
        out = StringIO()
        call_command("cleanup_expired_appointments", stdout=out)

        self.assertIsNone(
            Appointment.all_objects.get(pk=self.appt_in_progress.pk).deleted_at,
        )

    def test_preserves_completed(self):
        """COMPLETED → no se elimina."""
        out = StringIO()
        call_command("cleanup_expired_appointments", stdout=out)

        self.assertIsNone(
            Appointment.all_objects.get(pk=self.appt_completed.pk).deleted_at,
        )

    # ── Today / Future ───────────────────────────────────────────────────

    def test_ignores_today(self):
        """Turno de hoy → no se elimina."""
        out = StringIO()
        call_command("cleanup_expired_appointments", stdout=out)

        self.assertIsNone(
            Appointment.all_objects.get(pk=self.appt_today.pk).deleted_at,
        )

    def test_ignores_future(self):
        """Turno futuro → no se elimina."""
        out = StringIO()
        call_command("cleanup_expired_appointments", stdout=out)

        self.assertIsNone(
            Appointment.all_objects.get(pk=self.appt_future.pk).deleted_at,
        )

    # ── Idempotent ──────────────────────────────────────────────────────

    def test_idempotent(self):
        """Segunda ejecución → 0 registros modificados."""
        out1 = StringIO()
        call_command("cleanup_expired_appointments", stdout=out1)

        out2 = StringIO()
        call_command("cleanup_expired_appointments", stdout=out2)
        output2 = out2.getvalue()

        # Should say 0
        self.assertIn("0 turnos expirados eliminados", output2)

    # ── Dry run ──────────────────────────────────────────────────────────

    def test_dry_run_lists_without_modifying(self):
        """--dry-run → lista candidatos, no modifica registros."""
        out = StringIO()
        call_command("cleanup_expired_appointments", dry_run=True, stdout=out)

        output = out.getvalue()
        self.assertIn("DRY RUN", output)
        self.assertIn("Expired Scheduled", output)
        self.assertIn("Expired Confirmed", output)

        # Verify no records were modified
        self.assertIsNone(
            Appointment.all_objects.get(pk=self.appt_expired_scheduled.pk).deleted_at,
        )

    # ── Skip already soft-deleted ────────────────────────────────────────

    def test_skip_already_soft_deleted(self):
        """Ya eliminado → skip (manejado por el default manager)."""
        # First run
        out1 = StringIO()
        call_command("cleanup_expired_appointments", stdout=out1)

        # Second run — should affect 0 records
        out2 = StringIO()
        call_command("cleanup_expired_appointments", stdout=out2)
        output2 = out2.getvalue()

        self.assertIn("0 turnos expirados eliminados", output2)
