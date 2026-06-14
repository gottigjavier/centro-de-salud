"""Tests for Professional CRUD views — GET/POST per role, permissions, edge cases."""
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.professionals.forms import ProfessionalResourceAssignmentForm
from apps.professionals.models import Professional


# ── Helpers ────────────────────────────────────────────────────────────────


class BaseViewTest(TestCase):
    """Reusable user creation + professional fixture for all view tests."""

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
        self.professional = Professional.objects.create(
            first_name="Juan",
            last_name="Pérez",
            specialty="cardiology",
            license_number="MP12345",
            email="juan@salud.com",
            phone="+54 11 5555-1234",
        )


# ── professional_list ──────────────────────────────────────────────────────


class ProfessionalListViewTest(BaseViewTest):
    """GET /professionals/ — any authenticated role → 200, guest → 302."""

    url = reverse("professionals:list")

    def test_admin_200(self):
        self._login(self.admin)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_secretary_200(self):
        self._login(self.secretary)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_professional_200(self):
        self._login(self.professional_user)
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
        self._login(self.professional_user)
        response = self.client.get(self.url)
        self.assertFalse(response.context["is_admin"])

    def test_empty_list_shows_message(self):
        Professional.objects.all().delete()
        self._login(self.admin)
        response = self.client.get(self.url)
        self.assertContains(response, "No hay profesionales")

    def test_pagination_20_per_page(self):
        self._login(self.admin)
        for i in range(25):
            Professional.objects.create(
                first_name=f"Prof{i}",
                last_name=f"Test{i}",
                license_number=f"MP{i:05d}",
            )
        response = self.client.get(self.url)
        self.assertEqual(len(response.context["professionals"]), 20)
        self.assertTrue(response.context["professionals"].has_next())

    def test_second_page(self):
        self._login(self.admin)
        for i in range(25):
            Professional.objects.create(
                first_name=f"Prof{i}",
                last_name=f"Test{i}",
                license_number=f"MP{i:05d}",
            )
        response = self.client.get(self.url, {"page": 2})
        self.assertEqual(len(response.context["professionals"]), 6)


# ── professional_detail ────────────────────────────────────────────────────


class ProfessionalDetailViewTest(BaseViewTest):
    """GET /professionals/{pk}/ — any authenticated role → 200, guest → 302, 404."""

    def test_admin_200(self):
        self._login(self.admin)
        response = self.client.get(
            reverse("professionals:detail", args=[self.professional.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_secretary_200(self):
        self._login(self.secretary)
        response = self.client.get(
            reverse("professionals:detail", args=[self.professional.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_professional_200(self):
        self._login(self.professional_user)
        response = self.client.get(
            reverse("professionals:detail", args=[self.professional.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_guest_302(self):
        response = self.client.get(
            reverse("professionals:detail", args=[self.professional.pk])
        )
        self.assertEqual(response.status_code, 302)

    def test_404(self):
        self._login(self.admin)
        response = self.client.get(
            reverse("professionals:detail", args=[99999])
        )
        self.assertEqual(response.status_code, 404)

    def test_context_contains_professional(self):
        self._login(self.admin)
        response = self.client.get(
            reverse("professionals:detail", args=[self.professional.pk])
        )
        self.assertEqual(response.context["professional"].pk, self.professional.pk)

    def test_admin_receives_assignment_form(self):
        self._login(self.admin)
        response = self.client.get(
            reverse("professionals:detail", args=[self.professional.pk])
        )
        self.assertIsNotNone(response.context["form"])
        self.assertIsInstance(response.context["form"], ProfessionalResourceAssignmentForm)

    def test_secretary_no_assignment_form(self):
        self._login(self.secretary)
        response = self.client.get(
            reverse("professionals:detail", args=[self.professional.pk])
        )
        self.assertIsNone(response.context["form"])

    def test_professional_no_assignment_form(self):
        self._login(self.professional_user)
        response = self.client.get(
            reverse("professionals:detail", args=[self.professional.pk])
        )
        self.assertIsNone(response.context["form"])

    def test_empty_assignments_shows_message(self):
        self._login(self.admin)
        response = self.client.get(
            reverse("professionals:detail", args=[self.professional.pk])
        )
        self.assertContains(response, "No tiene asignaciones horarias")


# ── professional_create ────────────────────────────────────────────────────


class ProfessionalCreateViewTest(BaseViewTest):
    """GET|POST /professionals/crear/ — admin only, others → 403/302."""

    url = reverse("professionals:create")

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
        self._login(self.professional_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_guest_get_302(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    # ── POST ───────────────────────────────────────────────────────────────

    PASSWORD = "testpass123"

    def test_admin_post_valid_302(self):
        self._login(self.admin)
        response = self.client.post(
            self.url,
            {
                "first_name": "María",
                "last_name": "González",
                "specialty": "pediatrics",
                "license_number": "MP54321",
                "email": "maria@salud.com",
                "phone": "+54 11 5555-1234",
                "password": self.PASSWORD,
                "confirm_password": self.PASSWORD,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Professional.objects.filter(license_number="MP54321").exists()
        )
        # Verificar que se creó el User
        prof = Professional.objects.get(license_number="MP54321")
        self.assertIsNotNone(prof.user)
        self.assertEqual(prof.user.role, "professional")

    def test_admin_post_invalid_200(self):
        self._login(self.admin)
        response = self.client.post(
            self.url,
            {
                "first_name": "",
                "last_name": "",
                "specialty": "general",
                "license_number": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "first_name", "Este campo es obligatorio.")

    def test_admin_post_duplicate_license_200(self):
        Professional.objects.create(
            first_name="Otra",
            last_name="Persona",
            license_number="MP54321",
        )
        self._login(self.admin)
        response = self.client.post(
            self.url,
            {
                "first_name": "María",
                "last_name": "González",
                "specialty": "pediatrics",
                "license_number": "MP54321",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ya existe un profesional con esta matrícula.")

    def test_secretary_post_403(self):
        self._login(self.secretary)
        response = self.client.post(
            self.url,
            {
                "first_name": "No",
                "last_name": "Debe",
                "specialty": "general",
                "license_number": "MP00000",
            },
        )
        self.assertEqual(response.status_code, 403)

    def test_professional_post_403(self):
        self._login(self.professional_user)
        response = self.client.post(
            self.url,
            {
                "first_name": "No",
                "last_name": "Debe",
                "specialty": "general",
                "license_number": "MP00000",
            },
        )
        self.assertEqual(response.status_code, 403)

    def test_guest_post_302(self):
        response = self.client.post(
            self.url,
            {
                "first_name": "Sin",
                "last_name": "Auth",
                "specialty": "general",
                "license_number": "MP00000",
            },
        )
        self.assertEqual(response.status_code, 302)


# ── professional_update ────────────────────────────────────────────────────


class ProfessionalUpdateViewTest(BaseViewTest):
    """GET|POST /professionals/{pk}/editar/ — admin only, others → 403/302."""

    def test_admin_get_200(self):
        self._login(self.admin)
        response = self.client.get(
            reverse("professionals:update", args=[self.professional.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_secretary_get_403(self):
        self._login(self.secretary)
        response = self.client.get(
            reverse("professionals:update", args=[self.professional.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_professional_get_403(self):
        self._login(self.professional_user)
        response = self.client.get(
            reverse("professionals:update", args=[self.professional.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_guest_get_302(self):
        response = self.client.get(
            reverse("professionals:update", args=[self.professional.pk])
        )
        self.assertEqual(response.status_code, 302)

    def test_get_404(self):
        self._login(self.admin)
        response = self.client.get(
            reverse("professionals:update", args=[99999])
        )
        self.assertEqual(response.status_code, 404)

    # ── POST ───────────────────────────────────────────────────────────────

    def test_admin_post_valid_302(self):
        self._login(self.admin)
        response = self.client.post(
            reverse("professionals:update", args=[self.professional.pk]),
            {
                "first_name": "Juan Carlos",
                "last_name": "Pérez Rodríguez",
                "specialty": "cardiology",
                "license_number": "MP12345",
                "email": "juancarlos@salud.com",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.professional.refresh_from_db()
        self.assertEqual(self.professional.first_name, "Juan Carlos")
        self.assertEqual(self.professional.last_name, "Pérez Rodríguez")

    def test_admin_post_invalid_200(self):
        self._login(self.admin)
        response = self.client.post(
            reverse("professionals:update", args=[self.professional.pk]),
            {
                "first_name": "",
                "last_name": "",
                "specialty": "general",
                "license_number": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "first_name", "Este campo es obligatorio.")

    def test_admin_post_duplicate_license_excluding_self(self):
        """Updating same professional should allow keeping same license."""
        self._login(self.admin)
        response = self.client.post(
            reverse("professionals:update", args=[self.professional.pk]),
            {
                "first_name": "Juan",
                "last_name": "Pérez",
                "specialty": "cardiology",
                "license_number": "MP12345",  # Same as original
            },
        )
        self.assertEqual(response.status_code, 302)  # Redirect = success

    def test_secretary_post_403(self):
        self._login(self.secretary)
        response = self.client.post(
            reverse("professionals:update", args=[self.professional.pk]),
            {
                "first_name": "No",
                "last_name": "Debe",
                "specialty": "general",
                "license_number": "MP00000",
            },
        )
        self.assertEqual(response.status_code, 403)


# ── professional_toggle_active ─────────────────────────────────────────────


class ProfessionalToggleActiveViewTest(BaseViewTest):
    """POST /professionals/{pk}/toggle-active/ — admin only, toggles is_active."""

    # ── GET muestra confirmación ──────────────────────────────────────────

    def test_admin_get_confirm_page(self):
        self._login(self.admin)
        response = self.client.get(
            reverse("professionals:toggle_active", args=[self.professional.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "professionals/professional_confirm_delete.html")
        self.assertContains(response, self.professional.last_name)

    # ── POST ───────────────────────────────────────────────────────────────

    def test_admin_post_toggles_to_inactive(self):
        self.assertTrue(self.professional.is_active)
        self._login(self.admin)
        self.client.post(
            reverse("professionals:toggle_active", args=[self.professional.pk])
        )
        self.professional.refresh_from_db()
        self.assertFalse(self.professional.is_active)

    def test_admin_post_toggles_back_to_active(self):
        self.professional.is_active = False
        self.professional.save()
        self._login(self.admin)
        self.client.post(
            reverse("professionals:toggle_active", args=[self.professional.pk])
        )
        self.professional.refresh_from_db()
        self.assertTrue(self.professional.is_active)

    def test_admin_post_redirects(self):
        self._login(self.admin)
        response = self.client.post(
            reverse("professionals:toggle_active", args=[self.professional.pk])
        )
        self.assertRedirects(response, reverse("professionals:list"))

    def test_secretary_post_403(self):
        self._login(self.secretary)
        response = self.client.post(
            reverse("professionals:toggle_active", args=[self.professional.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_professional_post_403(self):
        self._login(self.professional_user)
        response = self.client.post(
            reverse("professionals:toggle_active", args=[self.professional.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_guest_post_302(self):
        response = self.client.post(
            reverse("professionals:toggle_active", args=[self.professional.pk])
        )
        self.assertEqual(response.status_code, 302)

    def test_post_404(self):
        self._login(self.admin)
        response = self.client.post(
            reverse("professionals:toggle_active", args=[99999])
        )
        self.assertEqual(response.status_code, 404)
