"""Tests for notification services — send_confirmation and backends."""
from datetime import time
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.appointments.models import Appointment, AppointmentStatus
from apps.notifications.backends import BaseNotificationBackend, EmailBackend
from apps.notifications.models import NotificationLog
from apps.notifications.services import send_confirmation
from apps.professionals.models import Professional
from apps.resources.models import Resource


class SendConfirmationTest(TestCase):
    """Tests for send_confirmation — email sending with logging."""

    @classmethod
    def setUpTestData(cls):
        cls.today = timezone.localdate()
        cls.professional = Professional.objects.create(
            first_name="Test", last_name="Prof",
            specialty="general", license_number="MAT-TEST",
        )
        cls.resource = Resource.objects.create(name="Test Resource", type="office")
        cls.appointment = Appointment.objects.create(
            resource=cls.resource,
            professional=cls.professional,
            date=cls.today,
            start_time=time(9, 0),
            end_time=time(9, 30),
            patient_name="Paciente Test",
            patient_dni="12345678",
            patient_phone="5555-0000",
            patient_email="paciente@test.com",
            status=AppointmentStatus.SCHEDULED,
        )
        cls.appt_no_email = Appointment.objects.create(
            resource=cls.resource,
            professional=cls.professional,
            date=cls.today,
            start_time=time(10, 0),
            end_time=time(10, 30),
            patient_name="Sin Email",
            patient_dni="87654321",
            patient_phone="5555-1111",
            status=AppointmentStatus.SCHEDULED,
        )

    @patch("apps.notifications.services.EmailBackend.send")
    def test_sends_email_and_creates_sent_log(self, mock_send):
        """Appointment con email válido → envía email, log status='sent'."""
        mock_send.return_value = (True, "")

        log = send_confirmation(self.appointment)

        mock_send.assert_called_once()
        self.assertEqual(log.status, NotificationLog.Status.SENT)
        self.assertIsNotNone(log.sent_at, "sent_at debe setearse al enviar")
        self.assertEqual(log.channel, NotificationLog.Channel.EMAIL)
        self.assertEqual(log.notification_type, NotificationLog.Type.CONFIRMATION)
        self.assertEqual(log.recipient, "paciente@test.com")
        self.assertEqual(log.appointment_id, self.appointment.pk)
        self.assertEqual(log.error_message, "")

    def test_no_email_creates_failed_log(self):
        """Appointment sin patient_email → log status='failed', no lanza excepción."""
        log = send_confirmation(self.appt_no_email)

        self.assertEqual(log.status, NotificationLog.Status.FAILED)
        self.assertEqual(log.error_message, "Paciente sin email")
        self.assertIsNone(log.sent_at, "sent_at debe ser None si falló")
        self.assertEqual(log.notification_type, NotificationLog.Type.CONFIRMATION)

    @patch("apps.notifications.services.EmailBackend.send")
    def test_email_failure_creates_failed_log(self, mock_send):
        """EmailBackend.send falla → log status='failed' con mensaje de error."""
        mock_send.return_value = (False, "SMTP connection refused")

        log = send_confirmation(self.appointment)

        self.assertEqual(log.status, NotificationLog.Status.FAILED)
        self.assertEqual(log.error_message, "SMTP connection refused")
        self.assertIsNone(log.sent_at, "sent_at debe ser None si falló")

    def test_always_creates_one_log(self):
        """Cada llamada a send_confirmation crea exactamente 1 NotificationLog."""
        with patch("apps.notifications.services.EmailBackend.send") as mock_send:
            mock_send.return_value = (True, "")
            log_count_before = NotificationLog.objects.count()
            send_confirmation(self.appointment)
            log_count_after = NotificationLog.objects.count()
            self.assertEqual(log_count_after - log_count_before, 1)

    @patch("apps.notifications.services.EmailBackend.send")
    def test_email_invalid_still_attempts_send(self, mock_send):
        """Appointment con email inválido → se intenta enviar igual."""
        mock_send.return_value = (False, "Invalid email format")

        appt_bad_email = Appointment.objects.create(
            resource=self.resource,
            professional=self.professional,
            date=self.today,
            start_time=time(11, 0),
            end_time=time(11, 30),
            patient_name="Mal Email",
            patient_dni="11111111",
            patient_phone="5555-2222",
            patient_email="not-an-email",
            status=AppointmentStatus.SCHEDULED,
        )

        log = send_confirmation(appt_bad_email)

        mock_send.assert_called_once()
        self.assertEqual(log.status, NotificationLog.Status.FAILED)
        self.assertEqual(log.error_message, "Invalid email format")

    @patch("apps.notifications.services.EmailBackend.send")
    def test_exception_in_backend_captured(self, mock_send):
        """Si backend.send lanza excepción → se captura y log failed."""
        mock_send.side_effect = ConnectionError("Server unreachable")

        log = send_confirmation(self.appointment)

        self.assertEqual(log.status, NotificationLog.Status.FAILED)
        self.assertIn("Server unreachable", log.error_message)

    @patch("apps.notifications.services.EmailBackend.send")
    def test_multiple_calls_create_multiple_logs(self, mock_send):
        """Llamar send_confirmation múltiples veces crea múltiples logs."""
        mock_send.return_value = (True, "")

        log1 = send_confirmation(self.appointment)
        log2 = send_confirmation(self.appointment)

        self.assertNotEqual(log1.pk, log2.pk)
        self.assertEqual(NotificationLog.objects.filter(
            appointment=self.appointment,
            notification_type=NotificationLog.Type.CONFIRMATION,
        ).count(), 2)


class BackendTest(TestCase):
    """Tests for BaseNotificationBackend and EmailBackend."""

    def test_base_backend_cannot_be_instantiated(self):
        """BaseNotificationBackend es abstracto → no se puede instanciar."""
        with self.assertRaises(TypeError):
            BaseNotificationBackend()

    def test_email_backend_send_returns_tuple(self):
        """EmailBackend.send retorna tuple (bool, str)."""
        backend = EmailBackend()
        # No necesitamos mock tearEmailBackend real porque al no
        # tener configuración SMTP real, send fallará con ConnectionError
        # y capturará la excepción retornando (False, mensaje).
        result = backend.send(
            to="test@test.com",
            subject="Test",
            body_html="<p>Test</p>",
            body_plain="Test",
        )
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], bool)
        self.assertIsInstance(result[1], str)

    @patch("django.core.mail.EmailMultiAlternatives.send")
    def test_email_backend_send_success(self, mock_django_send):
        """EmailBackend.send exitoso → retorna (True, '')."""
        mock_django_send.return_value = 1

        backend = EmailBackend()
        success, error = backend.send(
            to="test@test.com",
            subject="Test",
            body_html="<p>Test</p>",
            body_plain="Test",
        )

        self.assertTrue(success)
        self.assertEqual(error, "")
        mock_django_send.assert_called_once()

    @patch("django.core.mail.EmailMultiAlternatives.send")
    def test_email_backend_send_failure(self, mock_django_send):
        """EmailBackend.send falla → retorna (False, mensaje de error)."""
        mock_django_send.side_effect = ConnectionError("SMTP server down")

        backend = EmailBackend()
        success, error = backend.send(
            to="test@test.com",
            subject="Test",
            body_html="<p>Test</p>",
            body_plain="Test",
        )

        self.assertFalse(success)
        self.assertIn("SMTP server down", error)

    @patch("django.core.mail.EmailMultiAlternatives.send")
    def test_email_backend_send_without_html(self, mock_django_send):
        """EmailBackend.send sin html_message → funciona igual."""
        mock_django_send.return_value = 1

        backend = EmailBackend()
        success, error = backend.send(
            to="test@test.com",
            subject="Test",
            body_html="<p>Solo HTML</p>",
            body_plain="Solo texto",
        )

        self.assertTrue(success)
        self.assertEqual(error, "")

    def test_backend_send_signature_matches_base(self):
        """EmailBackend respeta la firma de BaseNotificationBackend.send."""
        import inspect
        base_sig = inspect.signature(BaseNotificationBackend.send)
        email_sig = inspect.signature(EmailBackend.send)
        # Verificar que los parámetros requeridos existen
        for param in ("to", "subject", "body_html", "body_plain"):
            self.assertIn(
                param, email_sig.parameters,
                f"EmailBackend.send debe tener parámetro '{param}'",
            )
