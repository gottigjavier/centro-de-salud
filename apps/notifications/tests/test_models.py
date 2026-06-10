"""Tests for notification models — NotificationConfig and NotificationLog."""
from datetime import time

from django.test import TestCase
from django.utils import timezone

from apps.appointments.models import Appointment, AppointmentStatus
from apps.notifications.models import NotificationConfig, NotificationLog
from apps.professionals.models import Professional
from apps.resources.models import Resource


class NotificationConfigTest(TestCase):
    """Tests for NotificationConfig model — creation, defaults, nullability."""

    @classmethod
    def setUpTestData(cls):
        cls.resource = Resource.objects.create(name="Consultorio 1", type="office")

    def test_str_with_resource(self):
        """__str__ con recurso muestra el nombre del recurso."""
        config = NotificationConfig.objects.create(resource=self.resource)
        self.assertIn("Consultorio 1", str(config))

    def test_str_global(self):
        """__str__ sin recurso muestra 'Configuración global'."""
        config = NotificationConfig.objects.create()
        self.assertIn("Configuración global", str(config))

    def test_default_values(self):
        """Los valores por defecto son correctos."""
        config = NotificationConfig.objects.create(resource=self.resource)
        self.assertTrue(
            config.reminder_enabled,
            "reminder_enabled debería ser True por defecto",
        )
        self.assertTrue(
            config.email_enabled,
            "email_enabled debería ser True por defecto",
        )
        self.assertFalse(
            config.whatsapp_enabled,
            "whatsapp_enabled debería ser False por defecto",
        )
        self.assertEqual(
            config.reminder_before_minutes,
            1440,
            "reminder_before_minutes debería ser 1440 por defecto",
        )

    def test_resource_nullable(self):
        """El campo resource puede ser nulo (config global)."""
        config = NotificationConfig.objects.create()
        self.assertIsNone(config.resource)


class NotificationLogTest(TestCase):
    """Tests for NotificationLog model — creation, defaults, choices, ordering."""

    @classmethod
    def setUpTestData(cls):
        cls.today = timezone.localdate()
        cls.professional = Professional.objects.create(
            first_name="Test",
            last_name="Prof",
            specialty="general",
            license_number="MAT-TEST",
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
            status=AppointmentStatus.SCHEDULED,
        )

    def test_str_shows_channel_and_type(self):
        """__str__ muestra canal y tipo de notificación."""
        log = NotificationLog.objects.create(
            appointment=self.appointment,
            channel=NotificationLog.Channel.EMAIL,
            notification_type=NotificationLog.Type.CONFIRMATION,
            recipient="test@example.com",
            status=NotificationLog.Status.SENT,
            sent_at=timezone.now(),
        )
        self.assertIn("Email", str(log))
        self.assertIn("Confirmación", str(log))

    def test_default_status_pending(self):
        """El estado por defecto es 'pending'."""
        log = NotificationLog.objects.create(
            appointment=self.appointment,
            channel=NotificationLog.Channel.EMAIL,
            notification_type=NotificationLog.Type.CONFIRMATION,
            recipient="test@example.com",
        )
        self.assertEqual(log.status, "pending")

    def test_error_message_default_empty(self):
        """error_message por defecto es string vacío."""
        log = NotificationLog.objects.create(
            appointment=self.appointment,
            channel=NotificationLog.Channel.EMAIL,
            notification_type=NotificationLog.Type.CONFIRMATION,
            recipient="test@example.com",
        )
        self.assertEqual(log.error_message, "")

    def test_sent_at_default_none(self):
        """sent_at por defecto es None."""
        log = NotificationLog.objects.create(
            appointment=self.appointment,
            channel=NotificationLog.Channel.EMAIL,
            notification_type=NotificationLog.Type.CONFIRMATION,
            recipient="test@example.com",
        )
        self.assertIsNone(log.sent_at)

    def test_status_choices(self):
        """Los choices de status son pending, sent, failed."""
        choices = dict(NotificationLog.Status.choices)
        for expected in ("pending", "sent", "failed"):
            self.assertIn(expected, choices)

    def test_channel_choices(self):
        """Los choices de channel son email y whatsapp."""
        choices = dict(NotificationLog.Channel.choices)
        for expected in ("email", "whatsapp"):
            self.assertIn(expected, choices)

    def test_type_choices(self):
        """Los choices de notification_type son confirmation, reminder, cancellation."""
        choices = dict(NotificationLog.Type.choices)
        for expected in ("confirmation", "reminder", "cancellation"):
            self.assertIn(expected, choices)

    def test_created_at_auto_set(self):
        """created_at se asigna automáticamente al crear."""
        log = NotificationLog.objects.create(
            appointment=self.appointment,
            channel=NotificationLog.Channel.EMAIL,
            notification_type=NotificationLog.Type.CONFIRMATION,
            recipient="test@example.com",
        )
        self.assertIsNotNone(log.created_at)

    def test_default_ordering(self):
        """El orden por defecto es -created_at (más reciente primero)."""
        self.assertEqual(NotificationLog._meta.ordering, ["-created_at"])
