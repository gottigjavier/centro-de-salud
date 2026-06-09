"""Tests for HTMX interactions — schedule add/delete with HX-Request header."""
from datetime import time

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.resources.models import Resource, ResourceSchedule


class BaseHTMXTest(TestCase):
    """Shared fixtures for HTMX tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.password = "testpass123"

    def _create_user(self, role, email=None):
        """Create a User without calling create_user (no username field)."""
        if email is None:
            email = f"{role}@test.com"
        user = User(
            email=email,
            role=role,
            first_name=role.capitalize(),
        )
        user.set_password(self.password)
        user.save()
        return user

    def _login(self, user):
        self.client.login(email=user.email, password=self.password)

    def setUp(self):
        self.admin = self._create_user("admin", "admin@test.com")
        self.secretary = self._create_user("secretary", "secretary@test.com")
        self.professional = self._create_user(
            "professional", "prof@test.com"
        )
        self.resource = Resource.objects.create(
            name="Consultorio 1",
            type="office",
            location="Planta baja",
        )

    def _htmx_post(self, url, data=None):
        """Helper: POST with HX-Request header set."""
        return self.client.post(
            url,
            data=data or {},
            HTTP_HX_REQUEST="true",
        )


# ── schedule_add (HTMX) ────────────────────────────────────────────────────


class ScheduleAddHTMXTest(BaseHTMXTest):
    """POST /resources/{pk}/horarios/agregar/ — admin only, HTMX responses."""

    def _add_url(self):
        return reverse("resources:schedule_add", args=[self.resource.pk])

    def _valid_data(self, **overrides):
        data = {
            "day_of_week": 0,
            "start_time": "09:00",
            "end_time": "12:00",
            "slot_duration": 30,
            "max_appointments_per_slot": 2,
        }
        data.update(overrides)
        return data

    # ── Permission ─────────────────────────────────────────────────────────

    def test_admin_post_200(self):
        self._login(self.admin)
        response = self._htmx_post(
            self._add_url(),
            self._valid_data(day_of_week=1, start_time="09:00", end_time="12:00"),
        )
        self.assertEqual(response.status_code, 200)

    def test_secretary_post_403(self):
        self._login(self.secretary)
        response = self._htmx_post(self._add_url(), self._valid_data())
        self.assertEqual(response.status_code, 403)

    def test_professional_post_403(self):
        self._login(self.professional)
        response = self._htmx_post(self._add_url(), self._valid_data())
        self.assertEqual(response.status_code, 403)

    def test_guest_302(self):
        response = self._htmx_post(self._add_url(), self._valid_data())
        self.assertEqual(response.status_code, 302)

    # ── Success (valid data) ──────────────────────────────────────────────

    def test_valid_creates_schedule(self):
        self._login(self.admin)
        self._htmx_post(
            self._add_url(),
            self._valid_data(day_of_week=1, start_time="09:00", end_time="12:00"),
        )
        self.assertEqual(
            ResourceSchedule.objects.filter(resource=self.resource).count(), 1
        )

    def test_valid_renders_schedule_list_partial(self):
        self._login(self.admin)
        response = self._htmx_post(
            self._add_url(),
            self._valid_data(
                day_of_week=1,
                start_time="09:00",
                end_time="12:00",
            ),
        )
        self.assertContains(response, "schedule-list-container")
        self.assertContains(response, "Martes")  # day_of_week=1 → Martes

    # ── Invalid (overlap) returns 422 ─────────────────────────────────────

    def test_overlap_returns_422(self):
        """Existing: Wednesday 09:00–12:00. New: Wednesday 10:00–11:00 → 422.
        
        Avoids day_of_week=0 (Monday) which is falsy and bypasses the
        overlap check — see ``test_forms.ResourceScheduleFormTest``.
        """
        ResourceSchedule.objects.create(
            resource=self.resource,
            day_of_week=2,  # Wednesday (not falsy)
            start_time=time(9, 0),
            end_time=time(12, 0),
            slot_duration=30,
        )
        self._login(self.admin)
        response = self._htmx_post(
            self._add_url(),
            self._valid_data(
                day_of_week=2,  # Wednesday
                start_time="10:00",
                end_time="11:00",
            ),
        )
        self.assertEqual(response.status_code, 422)
        self.assertContains(response, "superpone", status_code=422)

    def test_invalid_returns_schedule_form_partial(self):
        """On 422, response should contain the form (not the list)."""
        self._login(self.admin)
        response = self._htmx_post(
            self._add_url(),
            self._valid_data(
                start_time="10:00",
                end_time="09:00",  # start > end → invalid
            ),
        )
        self.assertEqual(response.status_code, 422)
        self.assertContains(response, "anterior", status_code=422)

    # ── Second schedule on same day (non-overlapping) ─────────────────────

    def test_non_overlapping_same_day_adds_second_schedule(self):
        """Existing: Monday 09:00–12:00. New: Monday 13:00–15:00 → OK."""
        ResourceSchedule.objects.create(
            resource=self.resource,
            day_of_week=0,
            start_time=time(9, 0),
            end_time=time(12, 0),
            slot_duration=30,
        )
        self._login(self.admin)
        response = self._htmx_post(
            self._add_url(),
            self._valid_data(
                day_of_week=0,
                start_time="13:00",
                end_time="15:00",
            ),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            ResourceSchedule.objects.filter(
                resource=self.resource, is_active=True
            ).count(),
            2,
        )


# ── schedule_delete (HTMX) ──────────────────────────────────────────────


class ScheduleDeleteHTMXTest(BaseHTMXTest):
    """POST /resources/horarios/{pk}/eliminar/ — admin only, soft delete."""

    def setUp(self):
        super().setUp()
        self.schedule = ResourceSchedule.objects.create(
            resource=self.resource,
            day_of_week=0,
            start_time=time(9, 0),
            end_time=time(12, 0),
            slot_duration=30,
            max_appointments_per_slot=2,
            is_active=True,
        )

    def _delete_url(self):
        return reverse(
            "resources:schedule_delete", args=[self.schedule.pk]
        )

    # ── Permission ─────────────────────────────────────────────────────────

    def test_admin_post_200(self):
        self._login(self.admin)
        response = self._htmx_post(self._delete_url())
        self.assertEqual(response.status_code, 200)

    def test_secretary_post_403(self):
        self._login(self.secretary)
        response = self._htmx_post(self._delete_url())
        self.assertEqual(response.status_code, 403)

    def test_professional_post_403(self):
        self._login(self.professional)
        response = self._htmx_post(self._delete_url())
        self.assertEqual(response.status_code, 403)

    def test_guest_302(self):
        response = self._htmx_post(self._delete_url())
        self.assertEqual(response.status_code, 302)

    # ── Soft delete ───────────────────────────────────────────────────────

    def test_soft_delete_sets_is_active_false(self):
        self._login(self.admin)
        self._htmx_post(self._delete_url())
        self.schedule.refresh_from_db()
        self.assertFalse(self.schedule.is_active)

    def test_soft_delete_keeps_record_in_db(self):
        self._login(self.admin)
        self._htmx_post(self._delete_url())
        self.assertTrue(
            ResourceSchedule.objects.filter(pk=self.schedule.pk).exists()
        )

    def test_delete_renders_schedule_list_partial(self):
        self._login(self.admin)
        response = self._htmx_post(self._delete_url())
        self.assertContains(response, "No hay horarios")

    # ── 404 ───────────────────────────────────────────────────────────────

    def test_delete_nonexistent_404(self):
        self._login(self.admin)
        response = self._htmx_post(
            reverse("resources:schedule_delete", args=[99999])
        )
        self.assertEqual(response.status_code, 404)


# ── resource_toggle_active (HTMX) ──────────────────────────────────────────


class ResourceToggleActiveHTMXTest(BaseHTMXTest):
    """POST /resources/{pk}/toggle-active/ with HX-Request → renders partial."""

    def test_htmx_returns_partial_row(self):
        self._login(self.admin)
        response = self._htmx_post(
            reverse("resources:toggle_active", args=[self.resource.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Consultorio 1")
        self.resource.refresh_from_db()
        self.assertFalse(self.resource.is_active)
        # After toggle inactive, response should show "Inactivo"
        self.assertContains(response, "Inactivo")

    def test_htmx_non_admin_403(self):
        self._login(self.secretary)
        response = self._htmx_post(
            reverse("resources:toggle_active", args=[self.resource.pk])
        )
        self.assertEqual(response.status_code, 403)


# ── nonworkingday_delete (HTMX) ─────────────────────────────────────────


class NonWorkingDayDeleteHTMXTest(BaseHTMXTest):
    """POST /resources/feriados/{pk}/eliminar/ with HX-Request → HX-Trigger."""

    def setUp(self):
        super().setUp()
        from datetime import date
        from apps.resources.models import NonWorkingDay

        self.nwd = NonWorkingDay.objects.create(
            date=date(2024, 12, 25),
            reason="Navidad",
            is_recurring=True,
        )

    def test_htmx_returns_hx_trigger(self):
        self._login(self.admin)
        response = self._htmx_post(
            reverse("resources:nonworkingday_delete", args=[self.nwd.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["HX-Trigger"], "nonworkingday-updated"
        )

    def test_htmx_non_admin_403(self):
        self._login(self.secretary)
        response = self._htmx_post(
            reverse("resources:nonworkingday_delete", args=[self.nwd.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_htmx_hard_deletes(self):
        from apps.resources.models import NonWorkingDay

        self._login(self.admin)
        self._htmx_post(
            reverse("resources:nonworkingday_delete", args=[self.nwd.pk])
        )
        self.assertFalse(
            NonWorkingDay.objects.filter(pk=self.nwd.pk).exists()
        )
