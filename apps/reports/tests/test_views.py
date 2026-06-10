"""Tests for reports views — dashboard, widget partials, CSV exports, role scoping."""
from datetime import timedelta, time

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User, Role
from apps.appointments.models import Appointment, AppointmentStatus
from apps.professionals.models import Professional
from apps.resources.models import Resource


class ReportsDashboardViewTest(TestCase):
    """Tests for reports_dashboard — GET /reportes/."""

    @classmethod
    def setUpTestData(cls):
        cls.password = "testpass123"

        cls.admin = User(
            email="admin@test.com", role=Role.ADMIN, first_name="Admin",
        )
        cls.admin.set_password(cls.password)
        cls.admin.save()

        cls.prof_user = User(
            email="prof@test.com", role=Role.PROFESSIONAL, first_name="Prof",
        )
        cls.prof_user.set_password(cls.password)
        cls.prof_user.save()

        cls.resource = Resource.objects.create(name="Test Resource", is_active=True)
        cls.prof = Professional.objects.create(
            user=cls.prof_user,
            first_name="Test",
            last_name="Prof",
            license_number="DOC001",
            is_active=True,
        )

        today = timezone.localdate()
        Appointment.objects.create(
            resource=cls.resource,
            professional=cls.prof,
            date=today,
            start_time=time(9, 0),
            end_time=time(9, 30),
            patient_name="Test Patient",
            patient_dni="12345678",
            status=AppointmentStatus.SCHEDULED,
            created_by=cls.admin,
        )

    def _login(self, user):
        self.client.login(email=user.email, password=self.password)

    def test_admin_gets_200(self):
        self._login(self.admin)
        response = self.client.get(reverse("reports:dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_professional_gets_200(self):
        self._login(self.prof_user)
        response = self.client.get(reverse("reports:dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_guest_gets_302(self):
        response = self.client.get(reverse("reports:dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_invalid_date_returns_400(self):
        self._login(self.admin)
        response = self.client.get(
            reverse("reports:dashboard"),
            {"date_from": "not-a-date", "date_to": "2026-01-01"},
        )
        self.assertEqual(response.status_code, 400)

    def test_shows_date_filter(self):
        self._login(self.admin)
        response = self.client.get(reverse("reports:dashboard"))
        self.assertContains(response, "date_from")
        self.assertContains(response, "date_to")

    def test_shows_widget_containers(self):
        self._login(self.admin)
        response = self.client.get(reverse("reports:dashboard"))
        self.assertContains(response, "widget-profesionales")
        self.assertContains(response, "widget-cancelaciones")


class WidgetProfesionalesViewTest(TestCase):
    """Tests for widget_profesionales — HTMX partial endpoint."""

    @classmethod
    def setUpTestData(cls):
        cls.password = "testpass123"

        cls.admin = User(
            email="admin@test.com", role=Role.ADMIN, first_name="Admin",
        )
        cls.admin.set_password(cls.password)
        cls.admin.save()

        cls.prof_user = User(
            email="prof@test.com", role=Role.PROFESSIONAL, first_name="Prof",
        )
        cls.prof_user.set_password(cls.password)
        cls.prof_user.save()

        cls.prof_no_user = User(
            email="noprofile@test.com", role=Role.PROFESSIONAL, first_name="NoProfile",
        )
        cls.prof_no_user.set_password(cls.password)
        cls.prof_no_user.save()

        cls.resource = Resource.objects.create(name="Test", is_active=True)
        cls.prof = Professional.objects.create(
            user=cls.prof_user,
            first_name="Test",
            last_name="Prof",
            license_number="DOC001",
            is_active=True,
        )

        today = timezone.localdate()
        Appointment.objects.create(
            resource=cls.resource,
            professional=cls.prof,
            date=today,
            start_time=time(9, 0),
            end_time=time(9, 30),
            patient_name="P1",
            patient_dni="1111",
            status=AppointmentStatus.SCHEDULED,
            created_by=cls.admin,
        )
        Appointment.objects.create(
            resource=cls.resource,
            professional=cls.prof,
            date=today,
            start_time=time(10, 0),
            end_time=time(10, 30),
            patient_name="P2",
            patient_dni="2222",
            status=AppointmentStatus.COMPLETED,
            created_by=cls.admin,
        )

    def _login(self, user):
        self.client.login(email=user.email, password=self.password)

    def test_widget_returns_html(self):
        today = timezone.localdate()
        self._login(self.admin)
        response = self.client.get(
            reverse("reports:widget_profesionales"),
            {
                "date_from": (today - timedelta(days=30)).isoformat(),
                "date_to": today.isoformat(),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Prof")

    def test_widget_invalid_date_returns_400(self):
        self._login(self.admin)
        response = self.client.get(
            reverse("reports:widget_profesionales"),
            {"date_from": "invalid-date", "date_to": "2026-01-01"},
        )
        self.assertEqual(response.status_code, 400)

    def test_widget_respects_professional_scoping(self):
        today = timezone.localdate()
        self._login(self.prof_user)
        response = self.client.get(
            reverse("reports:widget_profesionales"),
            {
                "date_from": (today - timedelta(days=30)).isoformat(),
                "date_to": today.isoformat(),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "solo tus turnos")

    def test_widget_warns_no_profile(self):
        self._login(self.prof_no_user)
        response = self.client.get(reverse("reports:widget_profesionales"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No tenés un perfil de profesional")


class WidgetCancelacionesViewTest(TestCase):
    """Tests for widget_cancelaciones — HTMX partial endpoint."""

    @classmethod
    def setUpTestData(cls):
        cls.password = "testpass123"

        cls.admin = User(
            email="admin@test.com", role=Role.ADMIN, first_name="Admin",
        )
        cls.admin.set_password(cls.password)
        cls.admin.save()

        cls.resource = Resource.objects.create(name="Test", is_active=True)
        cls.prof = Professional.objects.create(
            first_name="Dr.",
            last_name="Test",
            license_number="DOC001",
            is_active=True,
        )

        today = timezone.localdate()
        Appointment.objects.create(
            resource=cls.resource,
            professional=cls.prof,
            date=today,
            start_time=time(9, 0),
            end_time=time(9, 30),
            patient_name="P1",
            patient_dni="1111",
            status=AppointmentStatus.COMPLETED,
            created_by=cls.admin,
        )
        Appointment.objects.create(
            resource=cls.resource,
            professional=cls.prof,
            date=today,
            start_time=time(10, 0),
            end_time=time(10, 30),
            patient_name="P2",
            patient_dni="2222",
            status=AppointmentStatus.CANCELLED,
            cancellation_reason="Test reason",
            created_by=cls.admin,
        )

    def _login(self, user):
        self.client.login(email=user.email, password=self.password)

    def test_shows_cancellation_rate(self):
        today = timezone.localdate()
        self._login(self.admin)
        response = self.client.get(
            reverse("reports:widget_cancelaciones"),
            {
                "date_from": (today - timedelta(days=1)).isoformat(),
                "date_to": today.isoformat(),
            },
        )
        self.assertEqual(response.status_code, 200)
        # 1 cancelled out of 2 total = 50%
        self.assertContains(response, "50")

    def test_shows_reasons(self):
        today = timezone.localdate()
        self._login(self.admin)
        response = self.client.get(
            reverse("reports:widget_cancelaciones"),
            {
                "date_from": (today - timedelta(days=1)).isoformat(),
                "date_to": today.isoformat(),
            },
        )
        self.assertContains(response, "Test reason")


class CSVExportViewTest(TestCase):
    """Tests for CSV export views."""

    @classmethod
    def setUpTestData(cls):
        cls.password = "testpass123"

        cls.admin = User(
            email="admin@test.com", role=Role.ADMIN, first_name="Admin",
        )
        cls.admin.set_password(cls.password)
        cls.admin.save()

        cls.resource = Resource.objects.create(name="Test", is_active=True)
        cls.prof = Professional.objects.create(
            first_name="Dr.",
            last_name="Test",
            license_number="DOC001",
            is_active=True,
        )
        today = timezone.localdate()
        Appointment.objects.create(
            resource=cls.resource,
            professional=cls.prof,
            date=today,
            start_time=time(9, 0),
            end_time=time(9, 30),
            patient_name="P1",
            patient_dni="1111",
            status=AppointmentStatus.COMPLETED,
            created_by=cls.admin,
        )

    def _login(self, user):
        self.client.login(email=user.email, password=self.password)

    def test_csv_profesionales_returns_csv(self):
        self._login(self.admin)
        response = self.client.get(reverse("reports:csv_profesionales"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("Content-Disposition", response)
        self.assertIn(".csv", response["Content-Disposition"])

    def test_csv_has_bom(self):
        self._login(self.admin)
        response = self.client.get(reverse("reports:csv_profesionales"))
        content = b"".join(response.streaming_content)
        self.assertTrue(content.startswith(b"\xef\xbb\xbf"))  # UTF-8 BOM

    def test_csv_has_headers(self):
        self._login(self.admin)
        response = self.client.get(reverse("reports:csv_profesionales"))
        content = b"".join(response.streaming_content)
        self.assertIn(b"Profesional", content)
