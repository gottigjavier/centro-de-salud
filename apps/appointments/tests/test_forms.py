"""Tests for Appointment forms — validation, overlap, past dates, cancel form."""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.appointments.forms import AppointmentForm, CancelAppointmentForm
from apps.appointments.models import Appointment, AppointmentStatus
from apps.professionals.models import Professional, ProfessionalResourceAssignment
from apps.resources.models import Resource, ResourceSchedule


class BaseFormTest(TestCase):
    """Shared fixtures for all form tests."""

    @classmethod
    def setUpTestData(cls):
        cls.today = timezone.localdate()
        cls.tomorrow = cls.today + timedelta(days=1)
        cls.day_of_week = cls.tomorrow.weekday()
        cls.password = "testpass123"

        # Users
        cls.admin = User(
            email="admin@test.com", role="admin", first_name="Admin",
        )
        cls.admin.set_password(cls.password)
        cls.admin.save()

        cls.secretary = User(
            email="secretary@test.com", role="secretary", first_name="Secretary",
        )
        cls.secretary.set_password(cls.password)
        cls.secretary.save()

        cls.prof_user = User(
            email="prof@test.com", role="professional", first_name="Prof",
        )
        cls.prof_user.set_password(cls.password)
        cls.prof_user.save()

        # Professionals
        cls.professional = Professional.objects.create(
            first_name="Juan",
            last_name="Perez",
            specialty="general",
            license_number="MAT123",
            user=cls.prof_user,
        )
        cls.prof_no_user = Professional.objects.create(
            first_name="Sin",
            last_name="Usuario",
            specialty="general",
            license_number="MAT999",
        )

        # Resource
        cls.resource = Resource.objects.create(
            name="Consultorio 1", type="office", max_capacity=2,
        )

        # Schedule for tomorrow's weekday
        cls.schedule = ResourceSchedule.objects.create(
            resource=cls.resource,
            day_of_week=cls.day_of_week,
            start_time="08:00",
            end_time="17:00",
            slot_duration=30,
            max_appointments_per_slot=2,
        )

        # Assignment for the professional
        cls.assignment = ProfessionalResourceAssignment.objects.create(
            professional=cls.professional,
            resource=cls.resource,
            day_of_week=cls.day_of_week,
            start_time="08:00",
            end_time="12:00",
        )

        # Existing appointment for overlap tests (tomorrow)
        cls.existing_appt = Appointment.objects.create(
            resource=cls.resource,
            professional=cls.professional,
            date=cls.tomorrow,
            start_time="09:00",
            end_time="09:30",
            patient_name="Paciente Existente",
            patient_dni="12345678",
            status=AppointmentStatus.SCHEDULED,
        )

    def make_form(self, data=None, **kwargs):
        """Create AppointmentForm with professional queryset populated."""
        form = AppointmentForm(data=data, **kwargs)
        form.fields["professional"].queryset = Professional.objects.all()
        return form


class AppointmentFormTest(BaseFormTest):
    """AppointmentForm validation — happy path, past dates, overlap, required fields."""

    def setUp(self):
        self.valid_data = {
            "resource": self.resource.pk,
            "date": self.tomorrow.isoformat(),
            "professional": self.professional.pk,
            "start_time": "10:00",
            "end_time": "10:30",
            "patient_name": "Nuevo Paciente",
            "patient_dni": "87654321",
            "patient_phone": "5555-1234",
            "patient_email": "paciente@test.com",
            "comments": "Test comment",
        }

    def test_valid_form(self):
        """Valid data → form is valid."""
        form = self.make_form(data=self.valid_data)
        self.assertTrue(form.is_valid())

    def test_past_date_invalid(self):
        """Date in the past → form error on start_time."""
        yesterday = (self.tomorrow - timedelta(days=2)).isoformat()
        data = {**self.valid_data, "date": yesterday}
        form = self.make_form(data=data)
        self.assertFalse(form.is_valid())
        self.assertFormError(
            form, "start_time", "No se pueden crear turnos en el pasado."
        )

    def test_start_after_end_invalid(self):
        """start_time > end_time → non-field validation error."""
        data = {**self.valid_data, "start_time": "11:00", "end_time": "10:00"}
        form = self.make_form(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn("anterior", str(form.errors).lower())

    def test_same_slot_allowed_with_capacity(self):
        """Same time as existing → allowed (max_per_slot=2, existing=1)."""
        data = {**self.valid_data, "start_time": "09:00", "end_time": "09:30"}
        form = self.make_form(data=data)
        self.assertTrue(form.is_valid())

    def test_non_overlapping_valid(self):
        """Same day, different non-overlapping time → valid."""
        data = {**self.valid_data, "start_time": "10:00", "end_time": "10:30"}
        form = self.make_form(data=data)
        self.assertTrue(form.is_valid())

    def test_patient_name_required(self):
        """Empty patient_name → field error."""
        data = {**self.valid_data, "patient_name": ""}
        form = self.make_form(data=data)
        self.assertFalse(form.is_valid())
        self.assertFormError(
            form,
            "patient_name",
            "El nombre del paciente debe tener al menos 2 caracteres.",
        )

    def test_patient_name_min_length(self):
        """patient_name shorter than 2 chars → field error."""
        data = {**self.valid_data, "patient_name": "A"}
        form = self.make_form(data=data)
        self.assertFalse(form.is_valid())
        self.assertFormError(
            form,
            "patient_name",
            "El nombre del paciente debe tener al menos 2 caracteres.",
        )

    def test_patient_dni_required(self):
        """Empty patient_dni → field error."""
        data = {**self.valid_data, "patient_dni": ""}
        form = self.make_form(data=data)
        self.assertFalse(form.is_valid())
        self.assertFormError(
            form, "patient_dni", "El DNI del paciente es obligatorio."
        )

    def test_professional_queryset_empty_default(self):
        """Form without args → professional queryset is .none()."""
        form = AppointmentForm()
        self.assertEqual(len(form.fields["professional"].queryset), 0)

    def test_for_update_removes_fields(self):
        """Form with for_update=True → resource, date, etc. not in fields."""
        form = AppointmentForm(for_update=True)
        for field_name in ["resource", "date", "professional",
                           "start_time", "end_time", "status"]:
            self.assertNotIn(field_name, form.fields)
        # Patient fields should still be there
        self.assertIn("patient_name", form.fields)
        self.assertIn("patient_dni", form.fields)
        self.assertIn("comments", form.fields)

    def test_initial_status(self):
        """New form → initial status = SCHEDULED."""
        form = AppointmentForm()
        self.assertEqual(form.initial.get("status"), AppointmentStatus.SCHEDULED)

    def test_phone_required(self):
        """Empty phone is rejected."""
        data = {**self.valid_data, "patient_phone": ""}
        form = self.make_form(data=data)
        self.assertFalse(form.is_valid())
        self.assertFormError(
            form,
            "patient_phone",
            "El teléfono de contacto es obligatorio.",
        )

    def test_email_optional(self):
        """Empty email is accepted."""
        data = {**self.valid_data, "patient_email": ""}
        form = self.make_form(data=data)
        self.assertTrue(form.is_valid())


class CancelAppointmentFormTest(BaseFormTest):
    """CancelAppointmentForm — reason is required, max_length."""

    def test_cancel_form_valid(self):
        """Cancel form with reason → is_valid()."""
        form = CancelAppointmentForm(data={"reason": "Paciente canceló el turno."})
        self.assertTrue(form.is_valid())

    def test_cancel_form_missing_reason(self):
        """Cancel form without reason → invalid."""
        form = CancelAppointmentForm(data={"reason": ""})
        self.assertFalse(form.is_valid())
        self.assertIn("reason", form.errors)

    def test_cancel_form_reason_max_length(self):
        """Cancel form reason exceeds max_length → invalid."""
        form = CancelAppointmentForm(data={"reason": "x" * 501})
        self.assertFalse(form.is_valid())
        self.assertIn("reason", form.errors)
