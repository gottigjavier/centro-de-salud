"""Tests for Appointment models — custom manager, soft-delete, FK lookups."""
from datetime import time

from django.http import Http404
from django.shortcuts import get_object_or_404
from django.test import TestCase
from django.utils import timezone

from apps.appointments.models import Appointment, AppointmentStatus
from apps.notifications.models import NotificationLog
from apps.professionals.models import Professional
from apps.resources.models import Resource


class AppointmentManagerTest(TestCase):
    """Tests for AppointmentManager soft-delete behavior."""

    @classmethod
    def setUpTestData(cls):
        cls.today = timezone.localdate()
        cls.professional = Professional.objects.create(
            first_name="Manager", last_name="Test",
            specialty="general", license_number="MAT-MGR",
        )
        cls.resource = Resource.objects.create(name="Manager Resource", type="office")

        # Create 3 appointments
        cls.appt_1 = Appointment.objects.create(
            resource=cls.resource,
            professional=cls.professional,
            patient_name="Active 1",
            patient_dni="11111111",
            patient_phone="5555-0001",
            date=cls.today,
            start_time=time(9, 0),
            end_time=time(9, 30),
            status=AppointmentStatus.SCHEDULED,
        )
        cls.appt_2 = Appointment.objects.create(
            resource=cls.resource,
            professional=cls.professional,
            patient_name="Active 2",
            patient_dni="22222222",
            patient_phone="5555-0002",
            date=cls.today,
            start_time=time(10, 0),
            end_time=time(10, 30),
            status=AppointmentStatus.SCHEDULED,
        )
        cls.appt_3 = Appointment.objects.create(
            resource=cls.resource,
            professional=cls.professional,
            patient_name="To Delete",
            patient_dni="33333333",
            patient_phone="5555-0003",
            date=cls.today,
            start_time=time(11, 0),
            end_time=time(11, 30),
            status=AppointmentStatus.SCHEDULED,
        )

        # Soft-delete appt_3
        Appointment.all_objects.filter(pk=cls.appt_3.pk).update(
            deleted_at=timezone.now(),
        )

    # ── Default manager ─────────────────────────────────────────────────

    def test_default_manager_excludes_soft_deleted(self):
        """Appointment.objects.count() excluye soft-deleted."""
        self.assertEqual(Appointment.objects.count(), 2)

    def test_default_manager_get_on_deleted_raises(self):
        """Appointment.objects.get(pk=soft_deleted) → DoesNotExist."""
        with self.assertRaises(Appointment.DoesNotExist):
            Appointment.objects.get(pk=self.appt_3.pk)

    def test_all_objects_includes_soft_deleted(self):
        """Appointment.all_objects.count() incluye todos."""
        self.assertEqual(Appointment.all_objects.count(), 3)

    # ── New appointment ──────────────────────────────────────────────────

    def test_new_appointment_has_deleted_at_none(self):
        """Appointment.objects.create() → deleted_at=None."""
        appt = Appointment.objects.create(
            resource=self.resource,
            professional=self.professional,
            patient_name="Nuevo",
            patient_dni="44444444",
            patient_phone="5555-0004",
            date=self.today,
            start_time=time(12, 0),
            end_time=time(12, 30),
            status=AppointmentStatus.SCHEDULED,
        )
        self.assertIsNone(appt.deleted_at)

    # ── FK lookup ────────────────────────────────────────────────────────

    def test_fk_lookup_resolves_soft_deleted(self):
        """NotificationLog FK a Appointment soft-deleted → resuelve OK."""
        log = NotificationLog.objects.create(
            appointment=self.appt_3,  # Soft-deleted appointment
            channel=NotificationLog.Channel.EMAIL,
            notification_type=NotificationLog.Type.REMINDER,
            recipient="deleted@test.com",
            status=NotificationLog.Status.FAILED,
        )

        # FK lookup should work despite soft-delete
        fetched_log = NotificationLog.objects.get(pk=log.pk)
        self.assertEqual(fetched_log.appointment.pk, self.appt_3.pk)
        # The related appointment should have deleted_at set
        self.assertIsNotNone(fetched_log.appointment.deleted_at)

    # ── get_object_or_404 ────────────────────────────────────────────────

    def test_get_object_or_404_raises_for_soft_deleted(self):
        """get_object_or_404(Appointment, pk=soft_deleted) → Http404."""
        with self.assertRaises(Http404):
            get_object_or_404(Appointment, pk=self.appt_3.pk)

    def test_get_object_or_404_returns_active(self):
        """get_object_or_404(Appointment, pk=active) → returns appointment."""
        appt = get_object_or_404(Appointment, pk=self.appt_1.pk)
        self.assertEqual(appt.pk, self.appt_1.pk)
