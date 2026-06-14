"""Tests for Resource CRUD views — GET/POST per role, permissions, edge cases."""
from datetime import date, time
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.resources.models import NonWorkingDay, Resource, ResourceSchedule


# ── Helpers ────────────────────────────────────────────────────────────────


class BaseViewTest(TestCase):
    """Reusable user creation + resource fixture for all view tests."""

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
            max_capacity=2,
            description="Consulta general",
        )


# ── resource_list ──────────────────────────────────────────────────────────


class ResourceListViewTest(BaseViewTest):
    """GET /resources/ — any authenticated role → 200, guest → 302."""

    url = reverse("resources:list")

    def test_admin_200(self):
        self._login(self.admin)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_secretary_200(self):
        self._login(self.secretary)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_professional_200(self):
        self._login(self.professional)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_guest_302(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_context_is_admin_true_for_admin(self):
        self._login(self.admin)
        response = self.client.get(self.url)
        self.assertTrue(response.context["is_admin"])

    def test_context_is_admin_false_for_secretary(self):
        self._login(self.secretary)
        response = self.client.get(self.url)
        self.assertFalse(response.context["is_admin"])

    def test_context_is_admin_false_for_professional(self):
        self._login(self.professional)
        response = self.client.get(self.url)
        self.assertFalse(response.context["is_admin"])

    def test_empty_list_shows_message(self):
        Resource.objects.all().delete()
        self._login(self.admin)
        response = self.client.get(self.url)
        self.assertContains(response, "No hay recursos")

    def test_pagination_10_per_page(self):
        self._login(self.admin)
        for i in range(12):
            Resource.objects.create(name=f"Consultorio {i + 2}")
        response = self.client.get(self.url)
        self.assertEqual(len(response.context["resources"]), 10)
        self.assertTrue(response.context["resources"].has_next())

    def test_second_page(self):
        self._login(self.admin)
        for i in range(12):
            Resource.objects.create(name=f"Consultorio {i + 2}")
        response = self.client.get(self.url, {"page": 2})
        self.assertEqual(len(response.context["resources"]), 3)


# ── resource_detail ────────────────────────────────────────────────────────


class ResourceDetailViewTest(BaseViewTest):
    """GET /resources/{pk}/ — any authenticated role → 200, guest → 302, 404."""

    def test_admin_200(self):
        self._login(self.admin)
        response = self.client.get(
            reverse("resources:detail", args=[self.resource.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_secretary_200(self):
        self._login(self.secretary)
        response = self.client.get(
            reverse("resources:detail", args=[self.resource.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_professional_200(self):
        self._login(self.professional)
        response = self.client.get(
            reverse("resources:detail", args=[self.resource.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_guest_302(self):
        response = self.client.get(
            reverse("resources:detail", args=[self.resource.pk])
        )
        self.assertEqual(response.status_code, 302)

    def test_404(self):
        self._login(self.admin)
        response = self.client.get(
            reverse("resources:detail", args=[99999])
        )
        self.assertEqual(response.status_code, 404)

    def test_context_contains_resource(self):
        self._login(self.admin)
        response = self.client.get(
            reverse("resources:detail", args=[self.resource.pk])
        )
        self.assertEqual(response.context["resource"].pk, self.resource.pk)

    def test_admin_receives_schedule_form(self):
        self._login(self.admin)
        response = self.client.get(
            reverse("resources:detail", args=[self.resource.pk])
        )
        self.assertIsNotNone(response.context["form"])

    def test_secretary_no_schedule_form(self):
        self._login(self.secretary)
        response = self.client.get(
            reverse("resources:detail", args=[self.resource.pk])
        )
        self.assertIsNone(response.context["form"])

    def test_empty_schedules_shows_message(self):
        self._login(self.admin)
        response = self.client.get(
            reverse("resources:detail", args=[self.resource.pk])
        )
        self.assertContains(response, "No hay horarios")


# ── resource_create ────────────────────────────────────────────────────────


class ResourceCreateViewTest(BaseViewTest):
    """GET|POST /resources/crear/ — admin only, others → 403/302."""

    url = reverse("resources:create")

    # ── GET ────────────────────────────────────────────────────────────────

    def test_admin_get_200(self):
        self._login(self.admin)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_secretary_get_403(self):
        self._login(self.secretary)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_professional_get_403(self):
        self._login(self.professional)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_guest_get_302(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    # ── POST ───────────────────────────────────────────────────────────────

    def test_admin_post_valid_302(self):
        self._login(self.admin)
        response = self.client.post(
            self.url,
            {
                "name": "Consultorio Nuevo",
                "type": "office",
                "location": "Piso 1",
                "max_appointments_per_day": 50,
                "description": "Nuevo consultorio",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Resource.objects.filter(name="Consultorio Nuevo").exists()
        )

    def test_admin_post_invalid_200(self):
        self._login(self.admin)
        response = self.client.post(
            self.url,
            {
                "name": "",
                "type": "office",
                "location": "",
                "max_appointments_per_day": 1,
                "description": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "name", "Este campo es obligatorio.")

    def test_admin_post_duplicate_name_200(self):
        Resource.objects.create(name="Consultorio Duplicado")
        self._login(self.admin)
        response = self.client.post(
            self.url,
            {
                "name": "Consultorio Duplicado",
                "type": "office",
                "location": "",
                "max_appointments_per_day": 1,
                "description": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ya existe un recurso")

    def test_secretary_post_403(self):
        self._login(self.secretary)
        response = self.client.post(
            self.url,
            {
                "name": "No debería crear",
                "type": "office",
                "location": "",
                "max_appointments_per_day": 1,
                "description": "",
            },
        )
        self.assertEqual(response.status_code, 403)

    def test_professional_post_403(self):
        self._login(self.professional)
        response = self.client.post(
            self.url,
            {
                "name": "No debería crear",
                "type": "office",
                "location": "",
                "max_appointments_per_day": 1,
                "description": "",
            },
        )
        self.assertEqual(response.status_code, 403)

    def test_guest_post_302(self):
        response = self.client.post(
            self.url,
            {
                "name": "Sin auth",
                "type": "office",
                "location": "",
                "max_appointments_per_day": 1,
                "description": "",
            },
        )
        self.assertEqual(response.status_code, 302)


# ── resource_update ────────────────────────────────────────────────────────


class ResourceUpdateViewTest(BaseViewTest):
    """GET|POST /resources/{pk}/editar/ — admin only, others → 403/302."""

    def test_admin_get_200(self):
        self._login(self.admin)
        response = self.client.get(
            reverse("resources:update", args=[self.resource.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_secretary_get_403(self):
        self._login(self.secretary)
        response = self.client.get(
            reverse("resources:update", args=[self.resource.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_professional_get_403(self):
        self._login(self.professional)
        response = self.client.get(
            reverse("resources:update", args=[self.resource.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_guest_get_302(self):
        response = self.client.get(
            reverse("resources:update", args=[self.resource.pk])
        )
        self.assertEqual(response.status_code, 302)

    def test_get_404(self):
        self._login(self.admin)
        response = self.client.get(
            reverse("resources:update", args=[99999])
        )
        self.assertEqual(response.status_code, 404)

    # ── POST ───────────────────────────────────────────────────────────────

    def test_admin_post_valid_302(self):
        self._login(self.admin)
        response = self.client.post(
            reverse("resources:update", args=[self.resource.pk]),
            {
                "name": "Consultorio 1 Renovado",
                "type": "office",
                "location": "Piso 2",
                "max_appointments_per_day": 50,
                "description": "Actualizado",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.resource.refresh_from_db()
        self.assertEqual(self.resource.name, "Consultorio 1 Renovado")
        self.assertEqual(self.resource.max_appointments_per_day, 50)

    def test_admin_post_invalid_200(self):
        self._login(self.admin)
        response = self.client.post(
            reverse("resources:update", args=[self.resource.pk]),
            {
                "name": "",
                "type": "office",
                "location": "",
                "max_appointments_per_day": 1,
                "description": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "name", "Este campo es obligatorio.")

    def test_secretary_post_403(self):
        self._login(self.secretary)
        response = self.client.post(
            reverse("resources:update", args=[self.resource.pk]),
            {
                "name": "No debería",
                "type": "office",
                "location": "",
                "max_appointments_per_day": 1,
                "description": "",
            },
        )
        self.assertEqual(response.status_code, 403)


# ── resource_toggle_active ─────────────────────────────────────────────────


class ResourceToggleActiveViewTest(BaseViewTest):
    """POST /resources/{pk}/toggle-active/ — admin only, toggles is_active."""

    # ── GET muestra confirmación ──────────────────────────────────────────

    def test_admin_get_confirm_page(self):
        self._login(self.admin)
        response = self.client.get(
            reverse("resources:toggle_active", args=[self.resource.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "resources/resource_confirm_delete.html")
        self.assertContains(response, self.resource.name)

    # ── POST ───────────────────────────────────────────────────────────────

    def test_admin_post_toggles_to_inactive(self):
        self.assertTrue(self.resource.is_active)
        self._login(self.admin)
        self.client.post(
            reverse("resources:toggle_active", args=[self.resource.pk])
        )
        self.resource.refresh_from_db()
        self.assertFalse(self.resource.is_active)

    def test_admin_post_toggles_back_to_active(self):
        self.resource.is_active = False
        self.resource.save()
        self._login(self.admin)
        self.client.post(
            reverse("resources:toggle_active", args=[self.resource.pk])
        )
        self.resource.refresh_from_db()
        self.assertTrue(self.resource.is_active)

    def test_admin_post_redirects(self):
        self._login(self.admin)
        response = self.client.post(
            reverse("resources:toggle_active", args=[self.resource.pk])
        )
        self.assertRedirects(response, reverse("resources:list"))

    def test_secretary_post_403(self):
        self._login(self.secretary)
        response = self.client.post(
            reverse("resources:toggle_active", args=[self.resource.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_professional_post_403(self):
        self._login(self.professional)
        response = self.client.post(
            reverse("resources:toggle_active", args=[self.resource.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_guest_post_302(self):
        response = self.client.post(
            reverse("resources:toggle_active", args=[self.resource.pk])
        )
        self.assertEqual(response.status_code, 302)

    def test_post_404(self):
        self._login(self.admin)
        response = self.client.post(
            reverse("resources:toggle_active", args=[99999])
        )
        self.assertEqual(response.status_code, 404)


# ── nonworkingday_list ─────────────────────────────────────────────────────


class NonWorkingDayListViewTest(BaseViewTest):
    """GET /resources/feriados/ — admin & secretary → 200, professional → 403."""

    url = reverse("resources:nonworkingday_list")

    def test_admin_200(self):
        self._login(self.admin)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_secretary_200(self):
        self._login(self.secretary)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_professional_403(self):
        self._login(self.professional)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_guest_302(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_context_is_admin_true_for_admin(self):
        self._login(self.admin)
        response = self.client.get(self.url)
        self.assertTrue(response.context["is_admin"])

    def test_context_is_admin_false_for_secretary(self):
        self._login(self.secretary)
        response = self.client.get(self.url)
        self.assertFalse(response.context["is_admin"])

    def test_empty_list_shows_message(self):
        self._login(self.admin)
        response = self.client.get(self.url)
        self.assertContains(response, "No hay días no laborables")


# ── nonworkingday_create ───────────────────────────────────────────────────


class NonWorkingDayCreateViewTest(BaseViewTest):
    """GET|POST /resources/feriados/crear/ — admin only."""

    url = reverse("resources:nonworkingday_create")

    def test_admin_get_200(self):
        self._login(self.admin)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_secretary_get_403(self):
        self._login(self.secretary)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_professional_get_403(self):
        self._login(self.professional)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_guest_get_302(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_admin_post_valid_302(self):
        self._login(self.admin)
        response = self.client.post(
            self.url,
            {
                "date": "2026-12-25",
                "reason": "Navidad",
                "is_recurring": True,
            },
        )
        self.assertRedirects(
            response, reverse("resources:nonworkingday_list")
        )
        self.assertTrue(
            NonWorkingDay.objects.filter(date=date(2026, 12, 25)).exists()
        )

    def test_admin_post_invalid_200(self):
        self._login(self.admin)
        response = self.client.post(
            self.url,
            {
                "date": "",
                "reason": "",
                "is_recurring": False,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)
        self.assertTrue(response.context["form"].errors)


# ── nonworkingday_delete ──────────────────────────────────────────────────


class NonWorkingDayDeleteViewTest(BaseViewTest):
    """POST /resources/feriados/{pk}/eliminar/ — admin only (hard delete)."""

    def setUp(self):
        super().setUp()
        self.nwd = NonWorkingDay.objects.create(
            date=date(2026, 12, 25),
            reason="Navidad",
            is_recurring=True,
        )

    def test_admin_post_302(self):
        self._login(self.admin)
        response = self.client.post(
            reverse("resources:nonworkingday_delete", args=[self.nwd.pk])
        )
        self.assertRedirects(
            response, reverse("resources:nonworkingday_list")
        )
        self.assertFalse(
            NonWorkingDay.objects.filter(pk=self.nwd.pk).exists()
        )

    def test_secretary_post_403(self):
        self._login(self.secretary)
        response = self.client.post(
            reverse("resources:nonworkingday_delete", args=[self.nwd.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_professional_post_403(self):
        self._login(self.professional)
        response = self.client.post(
            reverse("resources:nonworkingday_delete", args=[self.nwd.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_guest_post_302(self):
        response = self.client.post(
            reverse("resources:nonworkingday_delete", args=[self.nwd.pk])
        )
        self.assertEqual(response.status_code, 302)

    def test_get_redirects_with_warning(self):
        """GET to delete view redirects with a warning message."""
        self._login(self.admin)
        response = self.client.get(
            reverse("resources:nonworkingday_delete", args=[self.nwd.pk])
        )
        self.assertEqual(response.status_code, 302)
        # Record should still exist (no delete on GET)
        self.assertTrue(
            NonWorkingDay.objects.filter(pk=self.nwd.pk).exists()
        )

    def test_post_404(self):
        self._login(self.admin)
        response = self.client.post(
            reverse("resources:nonworkingday_delete", args=[99999])
        )
        self.assertEqual(response.status_code, 404)
