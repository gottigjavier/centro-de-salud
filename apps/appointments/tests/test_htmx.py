"""Tests for HTMX endpoints — profesionales-por-recurso, horarios-por-profesional."""
from datetime import time as time_obj, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.appointments.models import Appointment, AppointmentStatus
from apps.professionals.models import Professional, ProfessionalResourceAssignment
from apps.resources.models import Resource, ResourceSchedule


class BaseHTMXTest(TestCase):
    """Shared fixtures for HTMX tests."""

    @classmethod
    def setUpTestData(cls):
        cls.today = timezone.localdate()
        cls.day_of_week = cls.today.weekday()
        cls.password = "testpass123"

        # Users
        cls.admin = User(
            email="admin@test.com", role="admin", first_name="Admin",
        )
        cls.admin.set_password(cls.password)
        cls.admin.save()

        cls.professional_user = User(
            email="prof@test.com", role="professional", first_name="Prof",
        )
        cls.professional_user.set_password(cls.password)
        cls.professional_user.save()

        # Professionals
        cls.professional = Professional.objects.create(
            first_name="Juan",
            last_name="Perez",
            specialty="cardiology",
            license_number="MAT001",
            user=cls.professional_user,
        )
        cls.prof_no_assign = Professional.objects.create(
            first_name="Sin",
            last_name="Asignacion",
            specialty="general",
            license_number="MAT002",
        )

        # Resources
        cls.resource = Resource.objects.create(
            name="Consultorio 1", type="office", max_capacity=2,
        )
        cls.resource_no_assign = Resource.objects.create(
            name="Consultorio Sin Asignacion", type="office",
        )

        # Schedule
        cls.schedule = ResourceSchedule.objects.create(
            resource=cls.resource,
            day_of_week=cls.day_of_week,
            start_time="08:00",
            end_time="17:00",
            slot_duration=30,
            max_appointments_per_slot=2,
        )

        # Assignment
        cls.assignment = ProfessionalResourceAssignment.objects.create(
            professional=cls.professional,
            resource=cls.resource,
            day_of_week=cls.day_of_week,
            start_time="08:00",
            end_time="12:00",
        )

    def _login(self, user):
        self.client.login(email=user.email, password=self.password)

    def _htmx_get(self, url, data=None):
        """Helper: GET with HX-Request header set."""
        return self.client.get(url, data=data or {}, HTTP_HX_REQUEST="true")


class ProfesionalesPorRecursoHTMXTest(BaseHTMXTest):
    """GET /appointments/htmx/profesionales-por-recurso/{resource_id}/."""

    def test_valid_request(self):
        """Valid resource+date → 200, contains professional select."""
        self._login(self.admin)
        url = reverse(
            "appointments:htmx_profesionales", args=[self.resource.pk]
        )
        response = self._htmx_get(url, {"date": self.today.isoformat()})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<select name="professional"')
        self.assertContains(response, "Juan")

    def test_missing_date(self):
        """No date param → message 'Seleccioná una fecha primero'."""
        self._login(self.admin)
        url = reverse(
            "appointments:htmx_profesionales", args=[self.resource.pk]
        )
        response = self._htmx_get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Seleccioná una fecha primero")

    def test_no_professionals_available(self):
        """Resource with no assignments → 'No hay profesionales disponibles'."""
        self._login(self.admin)
        url = reverse(
            "appointments:htmx_profesionales", args=[self.resource_no_assign.pk]
        )
        response = self._htmx_get(url, {"date": self.today.isoformat()})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No hay profesionales disponibles")

    def test_invalid_date(self):
        """Bad date format → 'Fecha inválida'."""
        self._login(self.admin)
        url = reverse(
            "appointments:htmx_profesionales", args=[self.resource.pk]
        )
        response = self._htmx_get(url, {"date": "not-a-date"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fecha inválida")

    def test_without_login_redirects(self):
        """Unauthenticated → 302."""
        url = reverse(
            "appointments:htmx_profesionales", args=[self.resource.pk]
        )
        response = self._htmx_get(url, {"date": self.today.isoformat()})
        self.assertEqual(response.status_code, 302)


class HorariosPorProfesionalHTMXTest(BaseHTMXTest):
    """GET /appointments/htmx/horarios-por-profesional/{professional_id}/."""

    def test_valid_request(self):
        """Valid params → 200, contains data-start-time and data-end-time."""
        self._login(self.admin)
        url = reverse(
            "appointments:htmx_horarios", args=[self.professional.pk]
        )
        response = self._htmx_get(url, {
            "date": self.today.isoformat(),
            "resource_id": self.resource.pk,
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<select name="slot"')
        self.assertContains(response, "data-start-time")
        self.assertContains(response, "data-end-time")

    def test_missing_params(self):
        """Missing date or resource_id → 'Faltan parámetros'."""
        self._login(self.admin)
        url = reverse(
            "appointments:htmx_horarios", args=[self.professional.pk]
        )
        response = self._htmx_get(url, {"date": self.today.isoformat()})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Faltan parámetros")

    def test_no_slots_available(self):
        """Professional not assigned → 'No hay horarios disponibles'."""
        self._login(self.admin)
        url = reverse(
            "appointments:htmx_horarios", args=[self.prof_no_assign.pk]
        )
        response = self._htmx_get(url, {
            "date": self.today.isoformat(),
            "resource_id": self.resource.pk,
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No hay horarios disponibles")

    def test_slots_exclude_booked(self):
        """Existing appointment at 09:00-09:30 → that slot is excluded."""
        # Create a booked appointment
        Appointment.objects.create(
            resource=self.resource,
            professional=self.professional,
            date=self.today,
            start_time="09:00",
            end_time="09:30",
            patient_name="Booked Patient",
            patient_dni="99999999",
            status=AppointmentStatus.SCHEDULED,
        )
        self._login(self.admin)
        url = reverse(
            "appointments:htmx_horarios", args=[self.professional.pk]
        )
        response = self._htmx_get(url, {
            "date": self.today.isoformat(),
            "resource_id": self.resource.pk,
        })
        self.assertEqual(response.status_code, 200)
        # 09:00 is booked → should NOT be in response
        self.assertNotContains(response, 'data-start-time="09:00"')
        # 08:00 should still be available
        self.assertContains(response, 'data-start-time="08:00"')

    def test_invalid_date(self):
        """Bad date → 'Fecha inválida'."""
        self._login(self.admin)
        url = reverse(
            "appointments:htmx_horarios", args=[self.professional.pk]
        )
        response = self._htmx_get(url, {
            "date": "not-a-date",
            "resource_id": self.resource.pk,
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fecha inválida")

    def test_without_login_redirects(self):
        """Unauthenticated → 302."""
        url = reverse(
            "appointments:htmx_horarios", args=[self.professional.pk]
        )
        response = self._htmx_get(url, {
            "date": self.today.isoformat(),
            "resource_id": self.resource.pk,
        })
        self.assertEqual(response.status_code, 302)


class AgendaHTMXTest(TestCase):
    """Test HTMX agenda partials — stats, table, HX-Trigger, row swap."""

    @classmethod
    def setUpTestData(cls):
        cls.today = timezone.localdate()
        cls.day_of_week = cls.today.weekday()
        cls.password = "testpass123"

        # Users
        cls.admin = User(
            email="admin@htmx.com", role="admin", first_name="Admin",
        )
        cls.admin.set_password(cls.password)
        cls.admin.save()

        cls.prof_user1 = User(
            email="prof1@htmx.com", role="professional", first_name="Prof1",
        )
        cls.prof_user1.set_password(cls.password)
        cls.prof_user1.save()

        # Professionals
        cls.prof1 = Professional.objects.create(
            user=cls.prof_user1, first_name="Dr.", last_name="García",
            specialty="cardiology", license_number="DOC001", is_active=True,
        )

        # Resource + Schedule
        cls.resource = Resource.objects.create(
            name="Consulta General", type="office", is_active=True,
        )
        ResourceSchedule.objects.create(
            resource=cls.resource, day_of_week=cls.day_of_week,
            start_time="08:00", end_time="17:00",
            slot_duration=30, max_appointments_per_slot=3,
        )
        # Tomorrow's schedule
        tomorrow_weekday = (cls.today + timedelta(days=1)).weekday()
        ResourceSchedule.objects.get_or_create(
            resource=cls.resource, day_of_week=tomorrow_weekday,
            defaults={
                "start_time": "08:00", "end_time": "17:00",
                "slot_duration": 30, "max_appointments_per_slot": 3,
            },
        )

        # ProfessionalResourceAssignment (required for V-008 validation)
        ProfessionalResourceAssignment.objects.create(
            professional=cls.prof1, resource=cls.resource,
            day_of_week=cls.day_of_week,
            start_time="08:00", end_time="17:00",
        )

        # Appointments for today
        Appointment.objects.create(
            resource=cls.resource, professional=cls.prof1,
            date=cls.today, start_time="09:00", end_time="09:30",
            patient_name="Paciente 1", patient_dni="11111111",
            status=AppointmentStatus.SCHEDULED,
        )
        Appointment.objects.create(
            resource=cls.resource, professional=cls.prof1,
            date=cls.today, start_time="09:30", end_time="10:00",
            patient_name="Paciente 2", patient_dni="22222222",
            status=AppointmentStatus.CONFIRMED,
        )

        # Appointment for tomorrow (should NOT appear in today's agenda)
        Appointment.objects.create(
            resource=cls.resource, professional=cls.prof1,
            date=cls.today + timedelta(days=1),
            start_time="09:00", end_time="09:30",
            patient_name="Paciente Futuro", patient_dni="44444444",
            status=AppointmentStatus.SCHEDULED,
        )

    def _login(self, user):
        self.client.login(email=user.email, password=self.password)

    def _htmx_get(self, url, data=None):
        """Helper: GET with HX-Request header set."""
        return self.client.get(url, data=data or {}, HTTP_HX_REQUEST="true")

    def test_stats_partial(self):
        """Stats partial returns cards with correct counts."""
        self._login(self.admin)
        response = self._htmx_get(reverse("appointments:agenda_stats"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Total")
        self.assertContains(response, "Programados")
        self.assertContains(response, "Confirmados")

    def test_table_partial(self):
        """Table partial returns grouped appointments."""
        self._login(self.admin)
        response = self._htmx_get(reverse("appointments:agenda_table"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "García")

    def test_transition_returns_hx_trigger(self):
        """HTMX transition response includes HX-Trigger header."""
        self._login(self.admin)
        appt = Appointment.objects.create(
            resource=self.resource,
            professional=self.prof1,
            date=self.today,
            start_time="10:00",
            end_time="10:30",
            patient_name="HX-Trigger Test",
            patient_dni="HT000001",
            status=AppointmentStatus.CONFIRMED,
        )
        response = self.client.post(
            reverse(
                "appointments:transition",
                args=[appt.pk, AppointmentStatus.ARRIVED.value],
            ),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("HX-Trigger", response)
        self.assertEqual(response["HX-Trigger"], "agenda-updated")

    def test_transition_returns_row_fragment(self):
        """HTMX transition returns _agenda_row.html fragment."""
        self._login(self.admin)
        appt = Appointment.objects.create(
            resource=self.resource,
            professional=self.prof1,
            date=self.today,
            start_time="10:00",
            end_time="10:30",
            patient_name="Row Fragment Test",
            patient_dni="RF000001",
            status=AppointmentStatus.CONFIRMED,
        )
        response = self.client.post(
            reverse(
                "appointments:transition",
                args=[appt.pk, AppointmentStatus.ARRIVED.value],
            ),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="row-')

    def test_empty_day_table(self):
        """Empty day table shows empty state."""
        self._login(self.admin)
        # Delete today's appointments
        Appointment.objects.filter(
            date=self.today, professional=self.prof1
        ).delete()
        response = self._htmx_get(reverse("appointments:agenda_table"))
        self.assertContains(response, "No hay turnos programados para hoy")
