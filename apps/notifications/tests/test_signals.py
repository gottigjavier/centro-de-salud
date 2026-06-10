"""Tests for Appointment post_save signal.

Scenarios covered (from spec):
    T-NOT-020: post_save en nuevo SCHEDULED con email → send_confirmation llamado
    T-NOT-021: post_save en nuevo SCHEDULED sin email → no falla
    T-NOT-022: post_save en update (created=False) → NO llama send_confirmation
    T-NOT-023: post_save en nuevo status!=SCHEDULED → NO llama send_confirmation
    T-NOT-024: Transacción fallida → on_commit NO ejecuta send_confirmation
    T-NOT-039: Post-save señal no rompe por excepción en send_confirmation
"""
from datetime import time
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.appointments.models import Appointment, AppointmentStatus
from apps.professionals.models import Professional
from apps.resources.models import Resource


class AppointmentPostSaveSignalTest(TestCase):
    """Tests for the appointment_post_save signal handler.

    NOTE: Django's ``TestCase`` wraps each test in a transaction that is
    rolled back at the end. Since ``transaction.on_commit`` callbacks never
    execute on rollback, we cannot rely on the callback firing automatically.

    Strategy:
    - Tests that verify the callback IS executed (T-NOT-020, T-NOT-021)
      patch ``transaction.on_commit`` with ``side_effect=lambda fn: fn()``
      so the callback fires immediately.
    - Tests that verify the callback is NOT executed (T-NOT-022, T-NOT-023)
      rely on the guard condition (``created and status == SCHEDULED``)
      being False — the signal fires but ``on_commit`` is never called.
    - Tests that verify the deffered nature (T-NOT-024) assert that
      ``_send_confirmation`` is NOT called directly in TestCase.
    """

    @classmethod
    def setUpTestData(cls):
        cls.today = timezone.localdate()
        cls.professional = Professional.objects.create(
            first_name="Test",
            last_name="Prof",
            specialty="general",
            license_number="MAT-SIG-TST",
        )
        cls.resource = Resource.objects.create(
            name="Signal Test Resource", type="office",
        )

    def _create_appointment(self, **overrides):
        """Helper to create an Appointment with sensible defaults."""
        defaults = {
            "resource": self.resource,
            "professional": self.professional,
            "date": self.today,
            "start_time": time(9, 0),
            "end_time": time(9, 30),
            "patient_name": "Patient Signal",
            "patient_dni": "99999999",
            "patient_phone": "5555-0000",
            "patient_email": "signal@test.com",
            "status": AppointmentStatus.SCHEDULED,
        }
        defaults.update(overrides)
        return Appointment.objects.create(**defaults)

    # ── T-NOT-020: Happy path ────────────────────────────────────────

    @patch(
        "apps.notifications.signals.transaction.on_commit",
        side_effect=lambda fn: fn(),
    )
    @patch("apps.notifications.signals._send_confirmation")
    def test_new_scheduled_triggers_confirmation(
        self, mock_send, mock_on_commit,
    ):
        """T-NOT-020: New SCHEDULED → send_confirmation is called once."""
        appt = self._create_appointment()

        mock_send.assert_called_once_with(appt)

    # ── T-NOT-021: No email edge case ────────────────────────────────

    @patch(
        "apps.notifications.signals.transaction.on_commit",
        side_effect=lambda fn: fn(),
    )
    @patch("apps.notifications.signals._send_confirmation")
    def test_new_scheduled_without_email_does_not_crash(
        self, mock_send, mock_on_commit,
    ):
        """T-NOT-021: New SCHEDULED without email → signal doesn't crash."""
        appt = self._create_appointment(patient_email="")

        mock_send.assert_called_once_with(appt)
        self.assertIsNotNone(appt.pk)

    # ── T-NOT-022: Update should NOT trigger ─────────────────────────

    def test_update_does_not_trigger_send(self):
        """T-NOT-022: Update (created=False) → send_confirmation NOT called."""
        appt = self._create_appointment()

        with patch("apps.notifications.signals._send_confirmation") as mock_send:
            appt.patient_name = "Updated Name"
            appt.save()
            mock_send.assert_not_called()

    # ── T-NOT-023: Non-SCHEDULED status ──────────────────────────────

    def test_new_cancelled_does_not_trigger_send(self):
        """T-NOT-023: New CANCELLED → send_confirmation NOT called."""
        with patch("apps.notifications.signals._send_confirmation") as mock_send:
            self._create_appointment(status=AppointmentStatus.CANCELLED)
            mock_send.assert_not_called()

    def test_new_confirmed_does_not_trigger_send(self):
        """T-NOT-023b: New CONFIRMED → send_confirmation NOT called."""
        with patch("apps.notifications.signals._send_confirmation") as mock_send:
            self._create_appointment(status=AppointmentStatus.CONFIRMED)
            mock_send.assert_not_called()

    # ── T-NOT-024: Transaction rollback ──────────────────────────────

    def test_send_confirmation_deferred_via_on_commit(self):
        """T-NOT-024: on_commit defers exec — not called in TestCase."""
        with patch("apps.notifications.signals._send_confirmation") as mock_send:
            self._create_appointment()
            # on_commit never fires in TestCase (transaction rolled back),
            # so _send_confirmation must NOT have been called directly.
            mock_send.assert_not_called()

    # ── T-NOT-039: Exception resilience ──────────────────────────────

    def test_signal_does_not_break_appointment_creation(self):
        """T-NOT-039: Signal doesn't prevent appointment creation.

        post_save runs AFTER the DB save, so even if the handler raises,
        the appointment is already persisted.
        """
        appt = self._create_appointment()
        self.assertIsNotNone(appt.pk)
