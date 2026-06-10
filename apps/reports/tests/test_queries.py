"""Tests for report aggregation queries — 6 query functions + _get_base_qs."""
from datetime import timedelta, time

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User, Role
from apps.appointments.models import Appointment, AppointmentStatus
from apps.professionals.models import Professional
from apps.resources.models import Resource


class BaseReportTest(TestCase):
    """Shared fixtures for all report query tests."""

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
            email="prof_nouser@test.com", role=Role.PROFESSIONAL, first_name="NoUser",
        )
        cls.prof_no_user.set_password(cls.password)
        cls.prof_no_user.save()

        cls.resource = Resource.objects.create(name="Consulta General", is_active=True)
        cls.resource2 = Resource.objects.create(name="Ecografía", is_active=True)

        cls.prof1 = Professional.objects.create(
            user=cls.prof_user,
            first_name="Dr.",
            last_name="García",
            license_number="DOC001",
            is_active=True,
        )
        cls.prof2 = Professional.objects.create(
            first_name="Dra.",
            last_name="López",
            license_number="DOC002",
            is_active=True,
        )

        today = timezone.localdate()

        # Create appointments across different dates
        dates = [today - timedelta(days=d) for d in [5, 10, 15, 20, 25]]

        cls.appts = []
        for i, d in enumerate(dates):
            statuses = [
                AppointmentStatus.SCHEDULED,
                AppointmentStatus.CONFIRMED,
                AppointmentStatus.ARRIVED,
                AppointmentStatus.IN_PROGRESS,
                AppointmentStatus.COMPLETED,
            ]
            cls.appts.append(Appointment.objects.create(
                resource=cls.resource,
                professional=cls.prof1 if i % 2 == 0 else cls.prof2,
                date=d,
                start_time=time(9, 0),
                end_time=time(9, 30),
                patient_name=f"Paciente {i}",
                patient_dni=f"{i:08d}",
                status=statuses[i % len(statuses)],
                created_by=cls.admin,
            ))

        # Add some cancelled appointments
        cls.cancelled_appt = Appointment.objects.create(
            resource=cls.resource,
            professional=cls.prof1,
            date=today - timedelta(days=3),
            start_time=time(10, 0),
            end_time=time(10, 30),
            patient_name="Cancelado",
            patient_dni="99999999",
            status=AppointmentStatus.CANCELLED,
            cancellation_reason="Paciente no pudo asistir",
            created_by=cls.admin,
        )

    def _login(self, user):
        self.client.login(email=user.email, password=self.password)


class GetProfesionalesReportTest(BaseReportTest):
    """Tests for get_profesionales_report()."""

    def test_admin_returns_all_professionals(self):
        from apps.reports.report_queries import get_profesionales_report

        today = timezone.localdate()
        data = get_profesionales_report(self.admin, today - timedelta(days=30), today)
        self.assertFalse(data["warning"])
        self.assertGreaterEqual(len(data["rows"]), 2)  # At least 2 professionals

    def test_professional_returns_only_own(self):
        from apps.reports.report_queries import get_profesionales_report

        today = timezone.localdate()
        data = get_profesionales_report(self.prof_user, today - timedelta(days=30), today)
        self.assertFalse(data["warning"])
        self.assertTrue(data["professional_only"])
        for row in data["rows"]:
            self.assertEqual(row["professional__id"], self.prof1.pk)

    def test_professional_without_user_returns_warning(self):
        from apps.reports.report_queries import get_profesionales_report

        today = timezone.localdate()
        data = get_profesionales_report(self.prof_no_user, today - timedelta(days=30), today)
        self.assertTrue(data["warning"])
        self.assertEqual(len(data["rows"]), 0)

    def test_counts_are_correct(self):
        from apps.reports.report_queries import get_profesionales_report

        today = timezone.localdate()
        data = get_profesionales_report(self.admin, today - timedelta(days=30), today)
        # prof1 has: 3 normal + 1 cancelled = 4 total
        prof1_data = [r for r in data["rows"] if r["professional__id"] == self.prof1.pk]
        statuses = ["scheduled", "confirmed", "arrived", "in_progress", "completed", "cancelled"]
        total_from_statuses = sum(prof1_data[0][s] for s in statuses)
        self.assertEqual(total_from_statuses, prof1_data[0]["total"])


class GetCancelacionesReportTest(BaseReportTest):
    """Tests for get_cancelaciones_report()."""

    def test_cancellation_rate(self):
        from apps.reports.report_queries import get_cancelaciones_report

        today = timezone.localdate()
        data = get_cancelaciones_report(self.admin, today - timedelta(days=30), today)
        self.assertGreater(data["cancelled"], 0)
        self.assertGreater(data["rate"], 0)

    def test_reasons_breakdown(self):
        from apps.reports.report_queries import get_cancelaciones_report

        today = timezone.localdate()
        data = get_cancelaciones_report(self.admin, today - timedelta(days=30), today)
        self.assertGreater(len(data["reasons"]), 0)
        self.assertIn(
            "Paciente no pudo asistir",
            [r["cancellation_reason"] for r in data["reasons"]],
        )

    def test_zero_cancellations(self):
        from apps.reports.report_queries import get_cancelaciones_report

        today = timezone.localdate()
        # Pick a day with a non-cancelled appointment only
        data = get_cancelaciones_report(self.admin, today - timedelta(days=5), today - timedelta(days=5))
        self.assertEqual(data["cancelled"], 0)
        self.assertEqual(data["rate"], 0.0)


class GetRecursosReportTest(BaseReportTest):
    """Tests for get_recursos_report()."""

    def test_admin_returns_all_resources(self):
        from apps.reports.report_queries import get_recursos_report

        today = timezone.localdate()
        data = get_recursos_report(self.admin, today - timedelta(days=30), today)
        self.assertGreater(len(data["rows"]), 0)

    def test_resource_counts(self):
        from apps.reports.report_queries import get_recursos_report

        today = timezone.localdate()
        data = get_recursos_report(self.admin, today - timedelta(days=30), today)
        total = sum(r["total"] for r in data["rows"])
        # recursos excludes cancelled and no_show
        total_appts = Appointment.objects.filter(
            date__gte=today - timedelta(days=30),
            date__lte=today,
        ).exclude(
            status__in=[AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW],
        ).count()
        self.assertEqual(total, total_appts)

    def test_unique_patients(self):
        from apps.reports.report_queries import get_recursos_report

        today = timezone.localdate()
        data = get_recursos_report(self.admin, today - timedelta(days=30), today)
        for row in data["rows"]:
            self.assertIn("unique_patients", row)
        if data["rows"]:
            self.assertGreaterEqual(data["rows"][0]["unique_patients"], 1)


class GetTendenciaReportTest(BaseReportTest):
    """Tests for get_tendencia_report()."""

    def test_returns_trend_data(self):
        from apps.reports.report_queries import get_tendencia_report

        today = timezone.localdate()
        data = get_tendencia_report(self.admin, today - timedelta(days=30), today)
        self.assertIsNotNone(data.get("labels"))
        self.assertIsNotNone(data.get("data"))
        self.assertEqual(len(data["labels"]), len(data["data"]))

    def test_daily_for_short_range(self):
        from apps.reports.report_queries import get_tendencia_report

        today = timezone.localdate()
        # 7 day range should be daily
        data = get_tendencia_report(self.admin, today - timedelta(days=7), today)
        self.assertTrue(data["is_daily"])

    def test_empty_periods_filled(self):
        from apps.reports.report_queries import get_tendencia_report

        today = timezone.localdate()
        date_from = today - timedelta(days=30)
        date_to = today
        data = get_tendencia_report(self.admin, date_from, date_to)

        expected_days = 31
        self.assertEqual(len(data["labels"]), expected_days)
        self.assertEqual(len(data["data"]), expected_days)

        total_count = sum(data["data"])
        expected_total = Appointment.objects.filter(
            date__gte=date_from, date__lte=date_to
        ).count()
        self.assertEqual(total_count, expected_total)

        self.assertTrue(any(v == 0 for v in data["data"]))


class GetFrecuentesReportTest(BaseReportTest):
    """Tests for get_frecuentes_report()."""

    def test_returns_patients(self):
        from apps.reports.report_queries import get_frecuentes_report

        today = timezone.localdate()
        data = get_frecuentes_report(self.admin, today - timedelta(days=30), today)
        self.assertGreater(len(data["rows"]), 0)
        # Each patient has unique name in test data
        first = data["rows"][0]
        self.assertIn("patient_name", first)
        self.assertIn("count", first)


class GetHorasPicoReportTest(BaseReportTest):
    """Tests for get_horas_pico_report()."""

    def test_returns_hours(self):
        from apps.reports.report_queries import get_horas_pico_report

        today = timezone.localdate()
        data = get_horas_pico_report(self.admin, today - timedelta(days=30), today)
        self.assertGreater(len(data["rows"]), 0)
        self.assertIn("label", data["rows"][0])
        self.assertIn("total", data["rows"][0])
