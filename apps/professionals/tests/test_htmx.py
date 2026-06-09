"""Tests for HTMX interactions — assignment add/delete with HX-Request header."""
from datetime import time

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.professionals.models import Professional, ProfessionalResourceAssignment
from apps.resources.models import Resource


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
        self.professional_user = self._create_user(
            "professional", "prof@test.com"
        )
        self.resource = Resource.objects.create(
            name="Consultorio 1",
            type="office",
            location="Planta baja",
        )
        self.professional = Professional.objects.create(
            first_name="Juan",
            last_name="Pérez",
            specialty="cardiology",
            license_number="MP12345",
        )

    def _htmx_post(self, url, data=None):
        """Helper: POST with HX-Request header set."""
        return self.client.post(
            url,
            data=data or {},
            HTTP_HX_REQUEST="true",
        )


# ── assignment_add (HTMX) ──────────────────────────────────────────────────


class AssignmentAddHTMXTest(BaseHTMXTest):
    """POST /professionals/{pk}/asignaciones/agregar/ — admin only, HTMX responses."""

    def _add_url(self):
        return reverse(
            "professionals:assignment_add", args=[self.professional.pk]
        )

    def _valid_data(self, **overrides):
        data = {
            "resource": self.resource.pk,
            "day_of_week": 1,
            "start_time": "09:00",
            "end_time": "12:00",
        }
        data.update(overrides)
        return data

    # ── Permission ─────────────────────────────────────────────────────────

    def test_admin_post_200(self):
        self._login(self.admin)
        response = self._htmx_post(
            self._add_url(),
            self._valid_data(),
        )
        self.assertEqual(response.status_code, 200)

    def test_secretary_post_403(self):
        self._login(self.secretary)
        response = self._htmx_post(self._add_url(), self._valid_data())
        self.assertEqual(response.status_code, 403)

    def test_professional_post_403(self):
        self._login(self.professional_user)
        response = self._htmx_post(self._add_url(), self._valid_data())
        self.assertEqual(response.status_code, 403)

    def test_guest_302(self):
        response = self._htmx_post(self._add_url(), self._valid_data())
        self.assertEqual(response.status_code, 302)

    def test_non_existent_professional_404(self):
        self._login(self.admin)
        url = reverse("professionals:assignment_add", args=[99999])
        response = self._htmx_post(url, self._valid_data())
        self.assertEqual(response.status_code, 404)

    # ── Success (valid data) ──────────────────────────────────────────────

    def test_valid_creates_assignment(self):
        self._login(self.admin)
        self._htmx_post(
            self._add_url(),
            self._valid_data(),
        )
        self.assertEqual(
            ProfessionalResourceAssignment.objects.filter(
                professional=self.professional
            ).count(),
            1,
        )

    def test_valid_renders_assignment_list_partial(self):
        self._login(self.admin)
        response = self._htmx_post(
            self._add_url(),
            self._valid_data(),
        )
        self.assertContains(response, "assignment-list-container")
        self.assertContains(response, "09:00")
        self.assertContains(response, "12:00")

    # ── Invalid (overlap) returns 422 ─────────────────────────────────────

    def test_overlap_returns_422(self):
        """Existing: Tuesday 09:00–12:00. New: Tuesday 10:00–11:00 → 422."""
        ProfessionalResourceAssignment.objects.create(
            professional=self.professional,
            resource=self.resource,
            day_of_week=1,
            start_time=time(9, 0),
            end_time=time(12, 0),
        )
        self._login(self.admin)
        response = self._htmx_post(
            self._add_url(),
            self._valid_data(
                start_time="10:00",
                end_time="11:00",
            ),
        )
        self.assertEqual(response.status_code, 422)
        self.assertContains(response, "superpone", status_code=422)

    def test_invalid_returns_assignment_form_partial(self):
        """On 422, response should contain the form (not the list)."""
        self._login(self.admin)
        response = self._htmx_post(
            self._add_url(),
            self._valid_data(
                start_time="12:00",
                end_time="09:00",  # start > end → invalid
            ),
        )
        self.assertEqual(response.status_code, 422)
        self.assertContains(response, "posterior", status_code=422)

    # ── Second assignment on same day (non-overlapping) ───────────────────

    def test_non_overlapping_same_day_adds_second_assignment(self):
        """Existing: Tuesday 09:00–12:00. New: Tuesday 13:00–15:00 → OK."""
        ProfessionalResourceAssignment.objects.create(
            professional=self.professional,
            resource=self.resource,
            day_of_week=1,
            start_time=time(9, 0),
            end_time=time(12, 0),
        )
        self._login(self.admin)
        response = self._htmx_post(
            self._add_url(),
            self._valid_data(
                start_time="13:00",
                end_time="15:00",
            ),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            ProfessionalResourceAssignment.objects.filter(
                professional=self.professional, is_active=True
            ).count(),
            2,
        )


# ── assignment_delete (HTMX) ────────────────────────────────────────────────


class AssignmentDeleteHTMXTest(BaseHTMXTest):
    """POST /professionals/asignaciones/{pk}/eliminar/ — admin only, soft delete."""

    def setUp(self):
        super().setUp()
        self.assignment = ProfessionalResourceAssignment.objects.create(
            professional=self.professional,
            resource=self.resource,
            day_of_week=1,
            start_time=time(9, 0),
            end_time=time(12, 0),
            is_active=True,
        )

    def _delete_url(self):
        return reverse(
            "professionals:assignment_delete", args=[self.assignment.pk]
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
        self._login(self.professional_user)
        response = self._htmx_post(self._delete_url())
        self.assertEqual(response.status_code, 403)

    def test_guest_302(self):
        response = self._htmx_post(self._delete_url())
        self.assertEqual(response.status_code, 302)

    # ── Soft delete ───────────────────────────────────────────────────────

    def test_soft_delete_sets_is_active_false(self):
        self._login(self.admin)
        self._htmx_post(self._delete_url())
        self.assignment.refresh_from_db()
        self.assertFalse(self.assignment.is_active)

    def test_soft_delete_keeps_record_in_db(self):
        self._login(self.admin)
        self._htmx_post(self._delete_url())
        self.assertTrue(
            ProfessionalResourceAssignment.objects.filter(
                pk=self.assignment.pk
            ).exists()
        )

    def test_delete_renders_assignment_list_partial(self):
        self._login(self.admin)
        response = self._htmx_post(self._delete_url())
        self.assertContains(response, "No tiene asignaciones horarias")

    # ── Idempotent delete ──────────────────────────────────────────────────

    def test_delete_already_inactive_is_idempotent(self):
        self.assignment.is_active = False
        self.assignment.save()
        self._login(self.admin)
        response = self._htmx_post(self._delete_url())
        self.assertEqual(response.status_code, 200)
        self.assignment.refresh_from_db()
        self.assertFalse(self.assignment.is_active)

    # ── 404 ───────────────────────────────────────────────────────────────

    def test_delete_nonexistent_404(self):
        self._login(self.admin)
        response = self._htmx_post(
            reverse("professionals:assignment_delete", args=[99999])
        )
        self.assertEqual(response.status_code, 404)
