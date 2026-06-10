"""Tests for Appointment CRUD views — GET/POST per role, permissions, transitions, scoping."""
from datetime import time, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.appointments.models import APPOINTMENT_VALID_TRANSITIONS, Appointment, AppointmentStatus
from apps.professionals.models import Professional, ProfessionalResourceAssignment
from apps.resources.models import Resource, ResourceSchedule


class BaseViewTest(TestCase):
    """Reusable fixtures for all view tests."""

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

        cls.secretary = User(
            email="secretary@test.com", role="secretary", first_name="Secretary",
        )
        cls.secretary.set_password(cls.password)
        cls.secretary.save()

        cls.professional_user = User(
            email="prof1@test.com", role="professional", first_name="Prof1",
        )
        cls.professional_user.set_password(cls.password)
        cls.professional_user.save()

        cls.another_prof_user = User(
            email="prof2@test.com", role="professional", first_name="Prof2",
        )
        cls.another_prof_user.set_password(cls.password)
        cls.another_prof_user.save()

        # Guest (no login) — no user record needed

        # Professionals
        cls.prof1 = Professional.objects.create(
            first_name="Juan",
            last_name="Perez",
            specialty="cardiology",
            license_number="MAT001",
            user=cls.professional_user,
        )
        cls.prof2 = Professional.objects.create(
            first_name="Ana",
            last_name="Gomez",
            specialty="pediatrics",
            license_number="MAT002",
            user=cls.another_prof_user,
        )
        cls.prof_no_user = Professional.objects.create(
            first_name="Sin",
            last_name="User",
            specialty="general",
            license_number="MAT003",
        )

        # Resource + Schedule + Assignment
        cls.resource = Resource.objects.create(
            name="Consultorio 1", type="office", max_capacity=2,
        )
        cls.schedule = ResourceSchedule.objects.create(
            resource=cls.resource,
            day_of_week=cls.day_of_week,
            start_time="08:00",
            end_time="17:00",
            slot_duration=30,
            max_appointments_per_slot=3,
        )
        cls.assignment = ProfessionalResourceAssignment.objects.create(
            professional=cls.prof1,
            resource=cls.resource,
            day_of_week=cls.day_of_week,
            start_time="08:00",
            end_time="17:00",
        )
        # Assignment for prof2 too
        cls.assignment2 = ProfessionalResourceAssignment.objects.create(
            professional=cls.prof2,
            resource=cls.resource,
            day_of_week=cls.day_of_week,
            start_time="08:00",
            end_time="17:00",
        )

        # Tomorrow fixtures for tests that need future dates
        cls.tomorrow = cls.today + timedelta(days=1)
        # Ensure the schedule covers tomorrow too
        ResourceSchedule.objects.get_or_create(
            resource=cls.resource,
            day_of_week=cls.tomorrow.weekday(),
            defaults={
                "start_time": "08:00",
                "end_time": "17:00",
                "slot_duration": 30,
                "max_appointments_per_slot": 3,
            },
        )
        ProfessionalResourceAssignment.objects.get_or_create(
            professional=cls.prof1,
            resource=cls.resource,
            day_of_week=cls.tomorrow.weekday(),
            defaults={
                "start_time": "08:00",
                "end_time": "17:00",
            },
        )
        ProfessionalResourceAssignment.objects.get_or_create(
            professional=cls.prof2,
            resource=cls.resource,
            day_of_week=cls.tomorrow.weekday(),
            defaults={
                "start_time": "08:00",
                "end_time": "17:00",
            },
        )

        # Appointments
        cls.appt1 = Appointment.objects.create(
            resource=cls.resource,
            professional=cls.prof1,
            date=cls.today,
            start_time="09:00",
            end_time="09:30",
            patient_name="Paciente Uno",
            patient_dni="11111111",
            status=AppointmentStatus.SCHEDULED,
        )
        cls.appt2 = Appointment.objects.create(
            resource=cls.resource,
            professional=cls.prof1,
            date=cls.today,
            start_time="10:00",
            end_time="10:30",
            patient_name="Paciente Dos",
            patient_dni="22222222",
            status=AppointmentStatus.CONFIRMED,
        )
        cls.appt3 = Appointment.objects.create(
            resource=cls.resource,
            professional=cls.prof2,
            date=cls.today,
            start_time="11:00",
            end_time="11:30",
            patient_name="Paciente Tres",
            patient_dni="33333333",
            status=AppointmentStatus.SCHEDULED,
        )

    def _login(self, user):
        self.client.login(email=user.email, password=self.password)


class AppointmentListViewTest(BaseViewTest):
    """GET /appointments/lista/ — role scoping, filters, pagination."""

    def test_admin_sees_all(self):
        """Admin sees appointments for all professionals (default filter = today)."""
        self._login(self.admin)
        response = self.client.get(reverse("appointments:list"))
        self.assertEqual(response.status_code, 200)
        appointments = list(response.context["appointments"])
        self.assertIn(self.appt1, appointments)
        self.assertIn(self.appt2, appointments)
        self.assertIn(self.appt3, appointments)

    def test_professional_sees_only_own(self):
        """Professional sees only own appointments."""
        self._login(self.professional_user)
        response = self.client.get(reverse("appointments:list"))
        self.assertEqual(response.status_code, 200)
        appointments = list(response.context["appointments"])
        self.assertIn(self.appt1, appointments)
        self.assertIn(self.appt2, appointments)
        self.assertNotIn(self.appt3, appointments)

    def test_professional_without_user_sees_warning(self):
        """Professional without linked profile sees warning and empty list."""
        # Create a user with no linked Professional
        orphan_user = User(
            email="orphan@test.com", role="professional", first_name="Orphan",
        )
        orphan_user.set_password(self.password)
        orphan_user.save()
        self.client.login(email="orphan@test.com", password=self.password)
        response = self.client.get(reverse("appointments:list"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["professional_warning"])
        self.assertEqual(len(list(response.context["appointments"])), 0)

    def test_guest_redirect(self):
        """Unauthenticated user → 302 (login redirect)."""
        response = self.client.get(reverse("appointments:list"))
        self.assertEqual(response.status_code, 302)

    def test_filter_by_date(self):
        """Filter by date_from shows only matching appointments."""
        future_date = self.today + timedelta(days=5)
        appt_future = Appointment.objects.create(
            resource=self.resource,
            professional=self.prof1,
            date=future_date,
            start_time="09:00",
            end_time="09:30",
            patient_name="Futuro Paciente",
            patient_dni="99999999",
            status=AppointmentStatus.SCHEDULED,
        )
        self._login(self.admin)
        response = self.client.get(
            reverse("appointments:list"),
            {"date_from": future_date.isoformat()},
        )
        self.assertEqual(response.status_code, 200)
        appointments = list(response.context["appointments"])
        self.assertIn(appt_future, appointments)
        self.assertNotIn(self.appt1, appointments)

    def test_filter_by_status(self):
        """Filter by status shows only matching appointments."""
        self._login(self.admin)
        response = self.client.get(
            reverse("appointments:list"),
            {"status": AppointmentStatus.CONFIRMED.value},
        )
        self.assertEqual(response.status_code, 200)
        appointments = list(response.context["appointments"])
        self.assertIn(self.appt2, appointments)
        self.assertNotIn(self.appt1, appointments)
        self.assertNotIn(self.appt3, appointments)

    def test_default_filter_today(self):
        """Default filter (no params) shows only today's appointments."""
        future_date = self.today + timedelta(days=5)
        Appointment.objects.create(
            resource=self.resource,
            professional=self.prof1,
            date=future_date,
            start_time="09:00",
            end_time="09:30",
            patient_name="Fuera de hoy",
            patient_dni="88888888",
            status=AppointmentStatus.SCHEDULED,
        )
        self._login(self.admin)
        response = self.client.get(reverse("appointments:list"))
        self.assertEqual(response.status_code, 200)
        appointments = list(response.context["appointments"])
        # Should only show today's appointments (appt1, appt2, appt3)
        self.assertEqual(len(appointments), 3)

    def test_pagination(self):
        """Pagination: 20 per page, page 1 has 20, page 2 has remainder."""
        self._login(self.admin)
        # Create 22 extra appointments (total 25 with existing 3)
        for i in range(22):
            Appointment.objects.create(
                resource=self.resource,
                professional=self.prof1,
                date=self.today,
                start_time="09:00",
                end_time="09:30",
                patient_name=f"Pag Paciente {i}",
                patient_dni=f"{i:08d}",
                status=AppointmentStatus.SCHEDULED,
            )
        response_page1 = self.client.get(reverse("appointments:list"))
        self.assertEqual(len(list(response_page1.context["appointments"])), 20)
        self.assertTrue(response_page1.context["appointments"].has_next())

        response_page2 = self.client.get(
            reverse("appointments:list"), {"page": 2}
        )
        appointments_page2 = list(response_page2.context["appointments"])
        self.assertEqual(len(appointments_page2), 5)
        self.assertFalse(response_page2.context["appointments"].has_next())

    def test_new_appointment_button_for_admin(self):
        """Admin sees the '+ Nuevo Turno' button."""
        self._login(self.admin)
        response = self.client.get(reverse("appointments:list"))
        self.assertContains(response, "Nuevo Turno")

    def test_new_appointment_button_for_secretary(self):
        """Secretary sees the '+ Nuevo Turno' button."""
        self._login(self.secretary)
        response = self.client.get(reverse("appointments:list"))
        self.assertContains(response, "Nuevo Turno")

    def test_no_new_appointment_button_for_professional(self):
        """Professional does NOT see the '+ Nuevo Turno' button."""
        self._login(self.professional_user)
        response = self.client.get(reverse("appointments:list"))
        self.assertNotContains(response, "Nuevo Turno")


class AppointmentDetailViewTest(BaseViewTest):
    """GET /appointments/{pk}/ — role scoping, 403, 404."""

    def test_admin_can_view_any(self):
        """Admin can view any appointment detail."""
        self._login(self.admin)
        response = self.client.get(
            reverse("appointments:detail", args=[self.appt1.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_professional_views_own(self):
        """Professional views own appointment detail."""
        self._login(self.professional_user)
        response = self.client.get(
            reverse("appointments:detail", args=[self.appt1.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_professional_views_others_403(self):
        """Professional viewing another's appointment → 403."""
        self._login(self.professional_user)
        response = self.client.get(
            reverse("appointments:detail", args=[self.appt3.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_guest_redirect(self):
        """Unauthenticated user → 302."""
        response = self.client.get(
            reverse("appointments:detail", args=[self.appt1.pk])
        )
        self.assertEqual(response.status_code, 302)

    def test_404(self):
        """Non-existent appointment → 404."""
        self._login(self.admin)
        response = self.client.get(
            reverse("appointments:detail", args=[99999])
        )
        self.assertEqual(response.status_code, 404)

    def test_context_contains_appointment(self):
        """Response context includes the appointment."""
        self._login(self.admin)
        response = self.client.get(
            reverse("appointments:detail", args=[self.appt1.pk])
        )
        self.assertEqual(response.context["appointment"].pk, self.appt1.pk)

    def test_context_contains_valid_transitions(self):
        """Context includes valid transitions for the current status."""
        self._login(self.admin)
        response = self.client.get(
            reverse("appointments:detail", args=[self.appt1.pk])
        )
        expected = APPOINTMENT_VALID_TRANSITIONS.get(AppointmentStatus.SCHEDULED)
        self.assertEqual(response.context["valid_transitions"], expected)


class AppointmentCreateViewTest(BaseViewTest):
    """GET|POST /appointments/crear/ — admin & secretary only, others 403/302."""

    url = reverse("appointments:create")

    # ── GET ──────────────────────────────────────────────────────────────

    def test_admin_get_200(self):
        self._login(self.admin)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_secretary_get_200(self):
        self._login(self.secretary)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_professional_get_403(self):
        self._login(self.professional_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_guest_get_302(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    # ── POST ─────────────────────────────────────────────────────────────

    def test_admin_post_valid_302(self):
        self._login(self.admin)
        response = self.client.post(
            self.url,
            {
                "resource": self.resource.pk,
                "date": self.tomorrow.isoformat(),
                "professional": self.prof1.pk,
                "start_time": "08:00",
                "end_time": "08:30",
                "patient_name": "Nuevo Paciente",
                "patient_dni": "87654321",
                "patient_phone": "5555-0000",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Appointment.objects.filter(patient_dni="87654321").exists()
        )

    def test_secretary_post_valid_302(self):
        self._login(self.secretary)
        response = self.client.post(
            self.url,
            {
                "resource": self.resource.pk,
                "date": self.tomorrow.isoformat(),
                "professional": self.prof1.pk,
                "start_time": "08:00",
                "end_time": "08:30",
                "patient_name": "Secretaria Paciente",
                "patient_dni": "11111111",
                "patient_phone": "5555-0001",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Appointment.objects.filter(patient_dni="11111111").exists()
        )

    def test_professional_post_403(self):
        self._login(self.professional_user)
        response = self.client.post(
            self.url,
            {
                "resource": self.resource.pk,
                "date": self.today.isoformat(),
                "professional": self.prof1.pk,
                "start_time": "08:00",
                "end_time": "08:30",
                "patient_name": "No Debería",
                "patient_dni": "00000000",
            },
        )
        self.assertEqual(response.status_code, 403)

    def test_guest_post_302(self):
        response = self.client.post(
            self.url,
            {
                "resource": self.resource.pk,
                "date": self.today.isoformat(),
                "professional": self.prof1.pk,
                "start_time": "08:00",
                "end_time": "08:30",
                "patient_name": "Sin Auth",
                "patient_dni": "00000000",
            },
        )
        self.assertEqual(response.status_code, 302)

    def test_admin_post_invalid_200(self):
        self._login(self.admin)
        response = self.client.post(
            self.url,
            {
                "resource": self.resource.pk,
                "date": self.today.isoformat(),
                "professional": self.prof1.pk,
                "start_time": "08:00",
                "end_time": "08:30",
                "patient_name": "",
                "patient_dni": "87654321",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)
        self.assertTrue(response.context["form"].errors)


class AppointmentUpdateViewTest(BaseViewTest):
    """GET|POST /appointments/{pk}/editar/ — admin & secretary only, partial edit."""

    # ── GET ──────────────────────────────────────────────────────────────

    def test_admin_get_200(self):
        self._login(self.admin)
        response = self.client.get(
            reverse("appointments:update", args=[self.appt1.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_secretary_get_200(self):
        self._login(self.secretary)
        response = self.client.get(
            reverse("appointments:update", args=[self.appt1.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_professional_get_403(self):
        self._login(self.professional_user)
        response = self.client.get(
            reverse("appointments:update", args=[self.appt1.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_guest_get_302(self):
        response = self.client.get(
            reverse("appointments:update", args=[self.appt1.pk])
        )
        self.assertEqual(response.status_code, 302)

    def test_get_404(self):
        self._login(self.admin)
        response = self.client.get(
            reverse("appointments:update", args=[99999])
        )
        self.assertEqual(response.status_code, 404)

    # ── POST ─────────────────────────────────────────────────────────────

    def test_admin_post_valid_302(self):
        self._login(self.admin)
        response = self.client.post(
            reverse("appointments:update", args=[self.appt1.pk]),
            {
                "patient_name": "Nombre Actualizado",
                "patient_dni": "11111111",
                "patient_phone": "5555-9999",
                "patient_email": "",
                "comments": "Comentario actualizado",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.appt1.refresh_from_db()
        self.assertEqual(self.appt1.patient_name, "Nombre Actualizado")
        self.assertEqual(self.appt1.comments, "Comentario actualizado")

    def test_secretary_post_valid_302(self):
        self._login(self.secretary)
        response = self.client.post(
            reverse("appointments:update", args=[self.appt1.pk]),
            {
                "patient_name": "Secretary Update",
                "patient_dni": "11111111",
                "patient_phone": "5555-1111",
                "patient_email": "",
                "comments": "",
            },
        )
        self.assertEqual(response.status_code, 302)

    def test_admin_post_invalid_200(self):
        self._login(self.admin)
        response = self.client.post(
            reverse("appointments:update", args=[self.appt1.pk]),
            {
                "patient_name": "",
                "patient_dni": "11111111",
                "patient_phone": "",
                "patient_email": "",
                "comments": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)
        self.assertTrue(response.context["form"].errors)

    def test_cannot_change_resource(self):
        """POST with different resource_id → resource stays unchanged."""
        other_resource = Resource.objects.create(
            name="Otro Consultorio", type="office",
        )
        self._login(self.admin)
        self.client.post(
            reverse("appointments:update", args=[self.appt1.pk]),
            {
                "patient_name": "Prueba Resource",
                "patient_dni": "11111111",
                "patient_phone": "5555-2222",
                "patient_email": "",
                "comments": "",
            },
        )
        self.appt1.refresh_from_db()
        self.assertEqual(self.appt1.resource.pk, self.resource.pk)


class AppointmentTransitionViewTest(BaseViewTest):
    """POST /appointments/{pk}/transition/{status}/ — state machine validation."""

    def setUp(self):
        # Create appointments in various states for transition tests
        # Times are in the afternoon to avoid conflicts with BaseViewTest fixtures (09:00-11:30)
        self.appt_scheduled = Appointment.objects.create(
            resource=self.resource,
            professional=self.prof1,
            date=self.today,
            start_time="12:00",
            end_time="12:30",
            patient_name="Scheduled Patient",
            patient_dni="S0000001",
            status=AppointmentStatus.SCHEDULED,
        )
        self.appt_confirmed = Appointment.objects.create(
            resource=self.resource,
            professional=self.prof1,
            date=self.today,
            start_time="12:30",
            end_time="13:00",
            patient_name="Confirmed Patient",
            patient_dni="C0000001",
            status=AppointmentStatus.CONFIRMED,
        )
        self.appt_in_progress = Appointment.objects.create(
            resource=self.resource,
            professional=self.prof1,
            date=self.today,
            start_time="13:00",
            end_time="13:30",
            patient_name="InProgress Patient",
            patient_dni="P0000001",
            status=AppointmentStatus.IN_PROGRESS,
        )
        self.appt_completed = Appointment.objects.create(
            resource=self.resource,
            professional=self.prof1,
            date=self.today,
            start_time="13:30",
            end_time="14:00",
            patient_name="Completed Patient",
            patient_dni="CP000001",
            status=AppointmentStatus.COMPLETED,
        )
        self.appt_cancelled = Appointment.objects.create(
            resource=self.resource,
            professional=self.prof1,
            date=self.today,
            start_time="14:00",
            end_time="14:30",
            patient_name="Cancelled Patient",
            patient_dni="CN000001",
            status=AppointmentStatus.CANCELLED,
        )

    # ── GET redirects to detail ──────────────────────────────────────────

    def test_get_redirects(self):
        """GET to transition endpoint → redirect to detail."""
        self._login(self.admin)
        response = self.client.get(
            reverse(
                "appointments:transition",
                args=[self.appt_scheduled.pk, AppointmentStatus.CONFIRMED.value],
            )
        )
        self.assertEqual(response.status_code, 302)

    # ── Valid transitions ────────────────────────────────────────────────

    def test_valid_transition_scheduled_to_confirmed(self):
        self._login(self.admin)
        response = self.client.post(
            reverse(
                "appointments:transition",
                args=[self.appt_scheduled.pk, AppointmentStatus.CONFIRMED.value],
            )
        )
        self.assertEqual(response.status_code, 302)
        self.appt_scheduled.refresh_from_db()
        self.assertEqual(self.appt_scheduled.status, AppointmentStatus.CONFIRMED.value)

    def test_valid_transition_confirmed_to_arrived(self):
        self._login(self.admin)
        response = self.client.post(
            reverse(
                "appointments:transition",
                args=[self.appt_confirmed.pk, AppointmentStatus.ARRIVED.value],
            )
        )
        self.assertEqual(response.status_code, 302)
        self.appt_confirmed.refresh_from_db()
        self.assertEqual(self.appt_confirmed.status, AppointmentStatus.ARRIVED.value)

    def test_valid_transition_arrived_to_in_progress(self):
        self._login(self.admin)
        # First transition to arrived, then to in_progress
        appt_arrived = Appointment.objects.create(
            resource=self.resource,
            professional=self.prof1,
            date=self.today,
            start_time="14:30",
            end_time="15:00",
            patient_name="Arrived Patient",
            patient_dni="AR000001",
            status=AppointmentStatus.ARRIVED,
        )
        response = self.client.post(
            reverse(
                "appointments:transition",
                args=[appt_arrived.pk, AppointmentStatus.IN_PROGRESS.value],
            )
        )
        self.assertEqual(response.status_code, 302)
        appt_arrived.refresh_from_db()
        self.assertEqual(appt_arrived.status, AppointmentStatus.IN_PROGRESS.value)

    def test_valid_transition_in_progress_to_completed(self):
        self._login(self.admin)
        response = self.client.post(
            reverse(
                "appointments:transition",
                args=[self.appt_in_progress.pk, AppointmentStatus.COMPLETED.value],
            )
        )
        self.assertEqual(response.status_code, 302)
        self.appt_in_progress.refresh_from_db()
        self.assertEqual(self.appt_in_progress.status, AppointmentStatus.COMPLETED.value)

    # ── Invalid transitions ──────────────────────────────────────────────

    def test_invalid_transition_scheduled_to_completed(self):
        """Skipping states (SCHEDULED → COMPLETED) → 400."""
        self._login(self.admin)
        response = self.client.post(
            reverse(
                "appointments:transition",
                args=[self.appt_scheduled.pk, AppointmentStatus.COMPLETED.value],
            )
        )
        self.assertEqual(response.status_code, 400)

    def test_invalid_transition_cancelled_to_scheduled(self):
        """Terminal state (CANCELLED) → can't transition → 400."""
        self._login(self.admin)
        response = self.client.post(
            reverse(
                "appointments:transition",
                args=[self.appt_cancelled.pk, AppointmentStatus.SCHEDULED.value],
            )
        )
        self.assertEqual(response.status_code, 400)

    def test_invalid_transition_completed_to_anything(self):
        """Terminal state (COMPLETED) → any transition → 400."""
        self._login(self.admin)
        response = self.client.post(
            reverse(
                "appointments:transition",
                args=[self.appt_completed.pk, AppointmentStatus.SCHEDULED.value],
            )
        )
        self.assertEqual(response.status_code, 400)

    # ── 404 ──────────────────────────────────────────────────────────────

    def test_transition_not_found(self):
        """Non-existent appointment → 404."""
        self._login(self.admin)
        response = self.client.post(
            reverse(
                "appointments:transition",
                args=[99999, AppointmentStatus.CONFIRMED.value],
            )
        )
        self.assertEqual(response.status_code, 404)

    # ── Professional scoping for transitions ─────────────────────────────

    def test_professional_transitions_own_scheduled_to_confirmed(self):
        """Professional can confirm their own appointment."""
        appt = Appointment.objects.create(
            resource=self.resource,
            professional=self.prof1,
            date=self.today,
            start_time="15:00",
            end_time="15:30",
            patient_name="Own Patient",
            patient_dni="OWN00001",
            status=AppointmentStatus.SCHEDULED,
        )
        self._login(self.professional_user)
        response = self.client.post(
            reverse(
                "appointments:transition",
                args=[appt.pk, AppointmentStatus.CONFIRMED.value],
            )
        )
        self.assertEqual(response.status_code, 302)

    def test_professional_cannot_transition_others(self):
        """Professional cannot transition another professional's appointment."""
        self._login(self.professional_user)
        response = self.client.post(
            reverse(
                "appointments:transition",
                args=[self.appt3.pk, AppointmentStatus.CONFIRMED.value],
            )
        )
        self.assertEqual(response.status_code, 403)

    # ── ARRIVED transition tests (C-2) ────────────────────────────────────

    def test_admin_transition_confirmed_to_arrived(self):
        """CONFIRMED → ARRIVED should work for admin."""
        appt = Appointment.objects.create(
            resource=self.resource,
            professional=self.prof1,
            date=self.today,
            start_time="15:00",
            end_time="15:30",
            patient_name="Arrival Test",
            patient_dni="AT000001",
            status=AppointmentStatus.CONFIRMED,
        )
        self._login(self.admin)
        response = self.client.post(
            reverse(
                "appointments:transition",
                args=[appt.pk, AppointmentStatus.ARRIVED.value],
            )
        )
        self.assertEqual(response.status_code, 302)
        appt.refresh_from_db()
        self.assertEqual(appt.status, AppointmentStatus.ARRIVED.value)

    def test_scheduled_to_arrived_invalid(self):
        """SCHEDULED → ARRIVED is not a valid transition."""
        appt = Appointment.objects.create(
            resource=self.resource,
            professional=self.prof1,
            date=self.today,
            start_time="15:00",
            end_time="15:30",
            patient_name="Bad Arrival",
            patient_dni="BA000001",
            status=AppointmentStatus.SCHEDULED,
        )
        self._login(self.admin)
        response = self.client.post(
            reverse(
                "appointments:transition",
                args=[appt.pk, AppointmentStatus.ARRIVED.value],
            )
        )
        self.assertEqual(response.status_code, 400)

    def test_arrived_to_in_progress_valid(self):
        """ARRIVED → IN_PROGRESS should work."""
        appt = Appointment.objects.create(
            resource=self.resource,
            professional=self.prof1,
            date=self.today,
            start_time="15:00",
            end_time="15:30",
            patient_name="Arrived To Progress",
            patient_dni="AP000001",
            status=AppointmentStatus.ARRIVED,
        )
        self._login(self.admin)
        response = self.client.post(
            reverse(
                "appointments:transition",
                args=[appt.pk, AppointmentStatus.IN_PROGRESS.value],
            )
        )
        self.assertEqual(response.status_code, 302)
        appt.refresh_from_db()
        self.assertEqual(appt.status, AppointmentStatus.IN_PROGRESS.value)

    def test_arrived_to_completed_invalid(self):
        """ARRIVED → COMPLETED is not valid."""
        appt = Appointment.objects.create(
            resource=self.resource,
            professional=self.prof1,
            date=self.today,
            start_time="15:00",
            end_time="15:30",
            patient_name="Skip Step",
            patient_dni="SS000001",
            status=AppointmentStatus.ARRIVED,
        )
        self._login(self.admin)
        response = self.client.post(
            reverse(
                "appointments:transition",
                args=[appt.pk, AppointmentStatus.COMPLETED.value],
            )
        )
        self.assertEqual(response.status_code, 400)

    def test_professional_cannot_mark_arrival(self):
        """Professional cannot do CONFIRMED → ARRIVED."""
        appt = Appointment.objects.create(
            resource=self.resource,
            professional=self.prof1,
            date=self.today,
            start_time="15:00",
            end_time="15:30",
            patient_name="Prof Cant Arrive",
            patient_dni="PCA00001",
            status=AppointmentStatus.CONFIRMED,
        )
        self._login(self.professional_user)
        response = self.client.post(
            reverse(
                "appointments:transition",
                args=[appt.pk, AppointmentStatus.ARRIVED.value],
            )
        )
        self.assertEqual(response.status_code, 403)

    def test_professional_can_start_from_arrived(self):
        """Professional can do ARRIVED → IN_PROGRESS."""
        appt = Appointment.objects.create(
            resource=self.resource,
            professional=self.prof1,
            date=self.today,
            start_time="15:00",
            end_time="15:30",
            patient_name="Prof Can Start",
            patient_dni="PCS00001",
            status=AppointmentStatus.ARRIVED,
        )
        self._login(self.professional_user)
        response = self.client.post(
            reverse(
                "appointments:transition",
                args=[appt.pk, AppointmentStatus.IN_PROGRESS.value],
            )
        )
        self.assertEqual(response.status_code, 302)
        appt.refresh_from_db()
        self.assertEqual(appt.status, AppointmentStatus.IN_PROGRESS.value)


class AppointmentCancelViewTest(BaseViewTest):
    """GET|POST /appointments/{pk}/cancelar/ — cancellation with reason."""

    # ── GET ──────────────────────────────────────────────────────────────

    def test_admin_get_200(self):
        self._login(self.admin)
        response = self.client.get(
            reverse("appointments:cancel", args=[self.appt1.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_secretary_get_200(self):
        self._login(self.secretary)
        response = self.client.get(
            reverse("appointments:cancel", args=[self.appt1.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_professional_get_200(self):
        """Professional can cancel own appointment."""
        self._login(self.professional_user)
        response = self.client.get(
            reverse("appointments:cancel", args=[self.appt1.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_professional_get_others_403(self):
        """Professional cannot cancel another's appointment."""
        self._login(self.professional_user)
        response = self.client.get(
            reverse("appointments:cancel", args=[self.appt3.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_guest_get_302(self):
        response = self.client.get(
            reverse("appointments:cancel", args=[self.appt1.pk])
        )
        self.assertEqual(response.status_code, 302)

    # ── POST ─────────────────────────────────────────────────────────────

    def test_admin_post_with_reason(self):
        """Admin cancels with reason → 302 + status CANCELLED + reason saved."""
        self._login(self.admin)
        response = self.client.post(
            reverse("appointments:cancel", args=[self.appt1.pk]),
            {"reason": "El paciente solicitó cancelación."},
        )
        self.assertEqual(response.status_code, 302)
        self.appt1.refresh_from_db()
        self.assertEqual(self.appt1.status, AppointmentStatus.CANCELLED.value)
        self.assertEqual(
            self.appt1.cancellation_reason, "El paciente solicitó cancelación."
        )

    def test_admin_post_without_reason(self):
        """Cancel without reason → form errors."""
        self._login(self.admin)
        response = self.client.post(
            reverse("appointments:cancel", args=[self.appt1.pk]),
            {"reason": ""},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)
        self.assertTrue(response.context["form"].errors)

    def test_professional_cancels_own(self):
        """Professional cancels own appointment → 302."""
        self._login(self.professional_user)
        response = self.client.post(
            reverse("appointments:cancel", args=[self.appt1.pk]),
            {"reason": "Cancelado por el profesional."},
        )
        self.assertEqual(response.status_code, 302)
        self.appt1.refresh_from_db()
        self.assertEqual(self.appt1.status, AppointmentStatus.CANCELLED.value)

    def test_professional_cancels_others_403(self):
        """Professional cancels another's → 403."""
        self._login(self.professional_user)
        response = self.client.post(
            reverse("appointments:cancel", args=[self.appt3.pk]),
            {"reason": "No debería poder."},
        )
        self.assertEqual(response.status_code, 403)

    def test_cancel_completed_appointment_returns_form_errors(self):
        """Cancel a completed appointment → model validation error → form rendered."""
        completed = Appointment.objects.create(
            resource=self.resource,
            professional=self.prof1,
            date=self.today,
            start_time="12:00",
            end_time="12:30",
            patient_name="Completed Pat",
            patient_dni="CP111111",
            status=AppointmentStatus.COMPLETED,
        )
        self._login(self.admin)
        response = self.client.post(
            reverse("appointments:cancel", args=[completed.pk]),
            {"reason": "Cancelación tardía."},
        )
        # Model validation prevents cancel of completed appointments
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)


class AgendaViewTest(TestCase):
    """Tests for agenda_view — scoping, stats, filters, empty state."""

    @classmethod
    def setUpTestData(cls):
        cls.today = timezone.localdate()
        cls.day_of_week = cls.today.weekday()
        cls.password = "testpass123"

        # Users
        cls.admin = User(
            email="admin@agenda.com", role="admin", first_name="Admin",
        )
        cls.admin.set_password(cls.password)
        cls.admin.save()

        cls.secretary = User(
            email="secre@agenda.com", role="secretary", first_name="Secre",
        )
        cls.secretary.set_password(cls.password)
        cls.secretary.save()

        cls.prof_user1 = User(
            email="prof1@agenda.com", role="professional", first_name="Prof1",
        )
        cls.prof_user1.set_password(cls.password)
        cls.prof_user1.save()

        cls.prof_user2 = User(
            email="prof2@agenda.com", role="professional", first_name="Prof2",
        )
        cls.prof_user2.set_password(cls.password)
        cls.prof_user2.save()

        cls.prof_nouser = User(
            email="prof_nouser@agenda.com", role="professional", first_name="NoUser",
        )
        cls.prof_nouser.set_password(cls.password)
        cls.prof_nouser.save()

        # Professionals
        cls.prof1 = Professional.objects.create(
            user=cls.prof_user1, first_name="Dr.", last_name="García",
            specialty="cardiology", license_number="DOC001", is_active=True,
        )
        cls.prof2 = Professional.objects.create(
            user=cls.prof_user2, first_name="Dra.", last_name="López",
            specialty="pediatrics", license_number="DOC002", is_active=True,
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
        # Also ensure tomorrow's schedule if needed
        tomorrow_weekday = (cls.today + timedelta(days=1)).weekday()
        ResourceSchedule.objects.get_or_create(
            resource=cls.resource, day_of_week=tomorrow_weekday,
            defaults={
                "start_time": "08:00", "end_time": "17:00",
                "slot_duration": 30, "max_appointments_per_slot": 3,
            },
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
        Appointment.objects.create(
            resource=cls.resource, professional=cls.prof2,
            date=cls.today, start_time="10:00", end_time="10:30",
            patient_name="Paciente 3", patient_dni="33333333",
            status=AppointmentStatus.IN_PROGRESS,
        )

        # Appointment for tomorrow (should NOT appear in agenda)
        cls.appt_tomorrow = Appointment.objects.create(
            resource=cls.resource, professional=cls.prof1,
            date=cls.today + timedelta(days=1),
            start_time="09:00", end_time="09:30",
            patient_name="Paciente Futuro", patient_dni="44444444",
            status=AppointmentStatus.SCHEDULED,
        )

    def _login(self, user):
        self.client.login(email=user.email, password=self.password)

    def test_admin_sees_all_today(self):
        """Admin sees all today's appointments."""
        self._login(self.admin)
        response = self.client.get(reverse("appointments:agenda"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Agenda del")

    def test_professional_sees_only_own(self):
        """Professional only sees their own appointments."""
        self._login(self.prof_user1)
        response = self.client.get(reverse("appointments:agenda"))
        self.assertEqual(response.status_code, 200)
        # Should see prof1's appointments (Paciente 1, Paciente 2)
        self.assertContains(response, "Paciente 1")
        self.assertContains(response, "Paciente 2")
        # Should NOT see prof2's appointments
        self.assertNotContains(response, "Paciente 3")

    def test_professional_without_user_shows_warning(self):
        """Professional without user profile sees warning."""
        self._login(self.prof_nouser)
        response = self.client.get(reverse("appointments:agenda"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context.get("professional_warning"))

    def test_guest_redirect(self):
        """Unauthenticated user gets 302."""
        response = self.client.get(reverse("appointments:agenda"))
        self.assertEqual(response.status_code, 302)

    def test_stats_in_context(self):
        """Stats are present in context."""
        self._login(self.admin)
        response = self.client.get(reverse("appointments:agenda"))
        self.assertIn("stats", response.context)
        stats = response.context["stats"]
        self.assertIn("total", stats)
        self.assertIn("scheduled", stats)
        self.assertIn("confirmed", stats)
        self.assertIn("arrived", stats)
        self.assertIn("in_progress", stats)
        self.assertIn("completed", stats)

    def test_filter_by_professional(self):
        """Filter by professional works."""
        self._login(self.admin)
        response = self.client.get(
            reverse("appointments:agenda"),
            {"professional": self.prof1.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Paciente 1")
        self.assertNotContains(response, "Paciente 3")

    def test_empty_day(self):
        """Day without appointments shows empty state."""
        # Create appointments ONLY for tomorrow, clear today's
        Appointment.objects.filter(date=self.today).delete()
        self._login(self.admin)
        response = self.client.get(reverse("appointments:agenda"))
        self.assertContains(response, "No hay turnos programados para hoy")
