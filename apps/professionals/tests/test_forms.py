"""Tests for Professional forms — validation, overlap detection, uniqueness."""
from datetime import date, time

from django.test import TestCase

from apps.professionals.forms import (
    ProfessionalForm,
    ProfessionalResourceAssignmentForm,
    _date_ranges_overlap,
)
from apps.professionals.models import Professional, ProfessionalResourceAssignment
from apps.resources.models import Resource


def _create_resource(**kwargs):
    """Helper to create a Resource."""
    defaults = {"name": "Test Resource", "type": "office"}
    defaults.update(kwargs)
    return Resource.objects.create(**defaults)


def _create_professional(**kwargs):
    """Helper to create a Professional."""
    defaults = {
        "first_name": "Juan",
        "last_name": "Pérez",
        "specialty": "general",
        "license_number": "MP12345",
    }
    defaults.update(kwargs)
    return Professional.objects.create(**defaults)


# ── _date_ranges_overlap ───────────────────────────────────────────────


class DateRangesOverlapTest(TestCase):
    """Unit tests for the _date_ranges_overlap helper function."""

    def test_both_none(self):
        self.assertTrue(_date_ranges_overlap(None, None, None, None))

    def test_both_defined_overlap(self):
        self.assertTrue(
            _date_ranges_overlap(
                date(2026, 1, 1), date(2026, 6, 30),
                date(2026, 3, 1), date(2026, 9, 30),
            )
        )

    def test_both_defined_no_overlap(self):
        self.assertFalse(
            _date_ranges_overlap(
                date(2026, 1, 1), date(2026, 6, 30),
                date(2026, 7, 1), date(2026, 12, 31),
            )
        )

    def test_adjacent_no_overlap(self):
        self.assertFalse(
            _date_ranges_overlap(
                date(2026, 1, 1), date(2026, 6, 30),
                date(2026, 6, 30), date(2026, 12, 31),
            )
        )

    def test_new_indefinite_overlaps_everything(self):
        self.assertTrue(
            _date_ranges_overlap(None, None, date(2026, 3, 1), date(2026, 9, 30))
        )

    def test_existing_indefinite_overlaps_everything(self):
        self.assertTrue(
            _date_ranges_overlap(
                date(2026, 3, 1), date(2026, 9, 30), None, None
            )
        )

    def test_new_no_end_touches_existing_start(self):
        """New has no end, existing ends after new starts."""
        self.assertTrue(
            _date_ranges_overlap(
                date(2026, 6, 1), None,
                date(2026, 3, 1), date(2026, 9, 30),
            )
        )

    def test_new_no_end_overlaps_existing_no_start(self):
        """Both have no end — they overlap indefinitely from the later start."""
        self.assertTrue(
            _date_ranges_overlap(
                date(2026, 1, 1), None,
                date(2026, 6, 30), None,
            )
        )

    def test_new_no_start_before_existing_end(self):
        """New has no start (open from past) — overlaps if existing hasn't ended."""
        self.assertTrue(
            _date_ranges_overlap(
                None, date(2026, 6, 30),
                date(2026, 3, 1), date(2026, 9, 30),
            )
        )


# ── ProfessionalForm ───────────────────────────────────────────────────


class ProfessionalFormTest(TestCase):
    """ProfessionalForm: license uniqueness (case insensitive, self-exclusion)."""

    PASSWORD = "testpass123"

    def setUp(self):
        self.valid_data = {
            "first_name": "María",
            "last_name": "González",
            "specialty": "pediatrics",
            "license_number": "MP54321",
            "email": "maria@salud.com",
            "phone": "+54 11 5555-1234",
            "password": self.PASSWORD,
            "confirm_password": self.PASSWORD,
        }

    def test_valid_form_creates_professional(self):
        form = ProfessionalForm(data=self.valid_data)
        self.assertTrue(form.is_valid())

    def test_clean_license_number_raises_on_duplicate(self):
        Professional.objects.create(
            first_name="Juan",
            last_name="Pérez",
            license_number="MP54321",
        )
        form = ProfessionalForm(data=self.valid_data)
        self.assertFalse(form.is_valid())
        self.assertIn(
            "Ya existe un profesional con esta matrícula.",
            form.errors["license_number"],
        )

    def test_clean_license_number_case_insensitive_duplicate(self):
        Professional.objects.create(
            first_name="Juan",
            last_name="Pérez",
            license_number="MP54321",
        )
        form = ProfessionalForm(
            data={**self.valid_data, "license_number": "mp54321"}
        )
        self.assertFalse(form.is_valid())
        self.assertIn(
            "Ya existe un profesional con esta matrícula.",
            form.errors["license_number"],
        )

    def test_clean_license_number_excludes_self_on_update(self):
        professional = Professional.objects.create(
            first_name="María",
            last_name="González",
            license_number="MP54321",
        )
        form = ProfessionalForm(
            data={**self.valid_data, "license_number": "MP54321"},
            instance=professional,
        )
        self.assertTrue(form.is_valid())

    def test_clean_license_number_allows_different(self):
        Professional.objects.create(
            first_name="Juan",
            last_name="Pérez",
            license_number="MP11111",
        )
        form = ProfessionalForm(data=self.valid_data)
        self.assertTrue(form.is_valid())

    def test_required_fields(self):
        form = ProfessionalForm(data={
            "first_name": "",
            "last_name": "",
            "specialty": "general",
            "license_number": "",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("first_name", form.errors)
        self.assertIn("last_name", form.errors)
        self.assertIn("license_number", form.errors)

    def test_create_with_minimal_data(self):
        """Should work without phone or resources. Email + password required for user creation."""
        form = ProfessionalForm(data={
            "first_name": "Ana",
            "last_name": "López",
            "specialty": "general",
            "license_number": "MP99999",
            "email": "ana@salud.com",
            "password": self.PASSWORD,
            "confirm_password": self.PASSWORD,
        })
        self.assertTrue(form.is_valid())
        professional = form.save()
        self.assertEqual(professional.phone, "")
        # Debe haber creado un User con role professional
        self.assertIsNotNone(professional.user)
        self.assertEqual(professional.user.role, "professional")
        self.assertEqual(professional.user.email, "ana@salud.com")


# ── ProfessionalResourceAssignmentForm ─────────────────────────────────


class ProfessionalResourceAssignmentFormTest(TestCase):
    """Overlap detection, validation for ProfessionalResourceAssignment form.

    NOTE: day_of_week=0 (Monday) is falsy in Python, so the form's overlap
    check uses `day is not None` — not `if day:`. All tests that need overlap
    use day_of_week=1 (Tuesday) to work around this.
    """

    def setUp(self):
        self.resource = _create_resource(name="Consultorio 1")
        self.professional = _create_professional()
        # Existing assignment: Tuesday (1) 09:00–12:00, indefinite
        self.existing = ProfessionalResourceAssignment.objects.create(
            professional=self.professional,
            resource=self.resource,
            day_of_week=1,
            start_time=time(9, 0),
            end_time=time(12, 0),
        )

    def _data(self, **overrides):
        """Return form data as strings (simulating HTTP POST)."""
        data = {
            "resource": self.resource.pk,
            "day_of_week": 1,
            "start_time": "10:00",
            "end_time": "11:00",
        }
        data.update(overrides)
        return data

    def _valid_form(self, **overrides):
        return ProfessionalResourceAssignmentForm(
            data=self._data(**overrides),
            professional=self.professional,
        )

    # ── start < end validation ─────────────────────────────────────────

    def test_start_equal_end_invalid(self):
        form = self._valid_form(start_time="09:00", end_time="09:00")
        self.assertFalse(form.is_valid())
        self.assertIn("posterior", str(form.errors).lower())

    def test_start_after_end_invalid(self):
        form = self._valid_form(start_time="14:00", end_time="13:00")
        self.assertFalse(form.is_valid())
        self.assertIn("posterior", str(form.errors).lower())

    def test_start_before_end_valid(self):
        form = self._valid_form(
            start_time="08:00", end_time="09:00",
            day_of_week=2,  # Different day to avoid overlap
        )
        self.assertTrue(form.is_valid())

    # ── end_date >= start_date validation ──────────────────────────────

    def test_end_date_before_start_date_invalid(self):
        form = self._valid_form(
            start_date="2026-12-01",
            end_date="2026-06-01",
            day_of_week=2,
            start_time="08:00",
            end_time="09:00",
        )
        self.assertFalse(form.is_valid())
        self.assertIn("anterior", str(form.errors).lower())

    def test_end_date_equals_start_date_valid(self):
        form = self._valid_form(
            start_date="2026-06-01",
            end_date="2026-06-01",
            day_of_week=2,
            start_time="08:00",
            end_time="09:00",
        )
        self.assertTrue(form.is_valid())

    # ── Overlap: partial at start ──────────────────────────────────────

    def test_overlap_partial_start(self):
        """New 08:00–10:00 overlaps with existing 09:00–12:00 at the start."""
        form = self._valid_form(start_time="08:00", end_time="10:00")
        self.assertFalse(form.is_valid())
        self.assertIn("superpone", str(form.errors).lower())

    # ── Overlap: partial at end ────────────────────────────────────────

    def test_overlap_partial_end(self):
        """New 11:00–13:00 overlaps with existing 09:00–12:00 at the end."""
        form = self._valid_form(start_time="11:00", end_time="13:00")
        self.assertFalse(form.is_valid())
        self.assertIn("superpone", str(form.errors).lower())

    # ── Overlap: new fully contained within existing ───────────────────

    def test_overlap_new_inside_existing(self):
        """New 10:00–11:00 is completely inside existing 09:00–12:00."""
        form = self._valid_form()
        self.assertFalse(form.is_valid())
        self.assertIn("superpone", str(form.errors).lower())

    # ── Overlap: existing fully contained within new ───────────────────

    def test_overlap_existing_inside_new(self):
        """New 08:00–13:00 completely contains existing 09:00–12:00."""
        form = self._valid_form(start_time="08:00", end_time="13:00")
        self.assertFalse(form.is_valid())
        self.assertIn("superpone", str(form.errors).lower())

    # ── Overlap: exact match ───────────────────────────────────────────

    def test_overlap_exact_match(self):
        """New 09:00–12:00 exactly matches existing."""
        form = self._valid_form(start_time="09:00", end_time="12:00")
        self.assertFalse(form.is_valid())
        self.assertIn("superpone", str(form.errors).lower())

    # ── Adjacent: end equals start (NOT overlap) ───────────────────────

    def test_adjacent_end_equals_start_is_valid(self):
        """New 12:00–15:00 is adjacent (end=start) — NOT overlap."""
        form = self._valid_form(start_time="12:00", end_time="15:00")
        self.assertTrue(form.is_valid())

    # ── Non-adjacent non-overlapping ───────────────────────────────────

    def test_non_overlapping_gap_is_valid(self):
        """New 13:00–15:00 has a gap after existing — NOT overlap."""
        form = self._valid_form(start_time="13:00", end_time="15:00")
        self.assertTrue(form.is_valid())

    # ── Different day is NOT overlap ───────────────────────────────────

    def test_different_day_is_valid(self):
        """Same time on different day (Wednesday) — NOT overlap."""
        form = self._valid_form(day_of_week=2)
        self.assertTrue(form.is_valid())

    # ── Different resource is NOT overlap ──────────────────────────────

    def test_different_resource_is_valid(self):
        """Same time, same day but different resource — NOT overlap."""
        other = _create_resource(name="Consultorio 2")
        form = self._valid_form(resource=other.pk)
        self.assertTrue(form.is_valid())

    # ── Different professional is NOT overlap ──────────────────────────

    def test_different_professional_is_valid(self):
        """Same resource, same day, same time — different professional."""
        other_prof = _create_professional(
            first_name="Ana", last_name="López",
            license_number="MP99999",
        )
        form = ProfessionalResourceAssignmentForm(
            data=self._data(),
            professional=other_prof,
        )
        self.assertTrue(form.is_valid())

    # ── day_of_week=0 (Monday) — NOT falsy ────────────────────────────

    def test_monday_overlap_is_detected(self):
        """day_of_week=0 (Lunes) — overlap se detecta correctamente."""
        monday_resource = _create_resource(name="Consultorio Monday")
        ProfessionalResourceAssignment.objects.create(
            professional=self.professional,
            resource=monday_resource,
            day_of_week=0,
            start_time=time(9, 0),
            end_time=time(12, 0),
        )
        form = ProfessionalResourceAssignmentForm(
            data={
                "resource": monday_resource.pk,
                "day_of_week": 0,
                "start_time": "10:00",
                "end_time": "11:00",
            },
            professional=self.professional,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("El horario se superpone", str(form.errors))

    # ── day_of_week=null (all days) ────────────────────────────────────

    def test_null_day_overlaps_with_specific_day(self):
        """Existing assignment has day_of_week=None (all days).
        New assignment on Tuesday should be rejected as overlap."""
        ProfessionalResourceAssignment.objects.create(
            professional=self.professional,
            resource=self.resource,
            day_of_week=None,
            start_time=time(9, 0),
            end_time=time(12, 0),
        )
        form = self._valid_form(day_of_week=1)
        self.assertFalse(form.is_valid())
        self.assertIn("superpone", str(form.errors).lower())

    # ── Date range overlap scenarios ───────────────────────────────────

    def test_non_overlapping_date_ranges_valid(self):
        """Different time AND different date range — no overlap.
        NOTE: UniqueConstraint forbids same professional+resource+day+start_time+end_time
        even with different date ranges, so we use different times."""
        self.existing.delete()  # Remove setUp's indefinite one FIRST
        ProfessionalResourceAssignment.objects.create(
            professional=self.professional,
            resource=self.resource,
            day_of_week=1,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 6, 30),
            start_time=time(9, 0),
            end_time=time(12, 0),
        )
        form = self._valid_form(
            start_date="2026-07-01",
            end_date="2026-12-31",
            start_time="13:00",  # Different time to avoid UniqueConstraint
            end_time="15:00",
        )
        self.assertTrue(form.is_valid())

    def test_overlapping_date_ranges_with_overlapping_time(self):
        """Overlapping date ranges AND overlapping times — overlap detected.
        Uses different times than existing to avoid UniqueConstraint."""
        self.existing.delete()  # Remove setUp's indefinite one FIRST
        ProfessionalResourceAssignment.objects.create(
            professional=self.professional,
            resource=self.resource,
            day_of_week=1,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            start_time=time(9, 0),
            end_time=time(12, 0),
        )
        form = self._valid_form(
            start_date="2026-06-01",
            end_date="2026-07-31",
            start_time="10:00",  # Different time, still overlaps with 09:00-12:00
            end_time="11:00",
        )
        self.assertFalse(form.is_valid())
        self.assertIn("superpone", str(form.errors).lower())

    # ── Edge: no professional passed ──────────────────────────────────

    def test_no_professional_skips_overlap_check(self):
        """Without a professional, overlap validation is skipped."""
        form = ProfessionalResourceAssignmentForm(
            data=self._data(),
        )
        self.assertTrue(form.is_valid())  # No professional, no overlap check
