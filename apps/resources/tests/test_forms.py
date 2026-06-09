"""Tests for Resource forms — validation, overlap detection, uniqueness."""
from datetime import date, time
from unittest.mock import patch

from django.test import TestCase

from apps.resources.forms import (
    NonWorkingDayForm,
    ResourceForm,
    ResourceScheduleForm,
)
from apps.resources.models import NonWorkingDay, Resource, ResourceSchedule


def _create_resource(**kwargs):
    """Helper to create a Resource. Accepts extra kwargs to override defaults."""
    defaults = {"name": "Test Resource", "type": "office"}
    defaults.update(kwargs)
    return Resource.objects.create(**defaults)


# ── ResourceForm ───────────────────────────────────────────────────────────


class ResourceFormTest(TestCase):
    """ResourceForm: clean_name uniqueness (case insensitive, self-exclusion)."""

    def setUp(self):
        self.valid_data = {
            "name": "Consultorio 1",
            "type": "office",
            "location": "Planta baja",
            "max_capacity": 2,
            "description": "Consultorio de atención general",
        }

    def test_valid_form_creates_resource(self):
        form = ResourceForm(data=self.valid_data)
        self.assertTrue(form.is_valid())

    def test_clean_name_raises_on_duplicate(self):
        Resource.objects.create(name="Consultorio 1")
        form = ResourceForm(data=self.valid_data)
        self.assertFalse(form.is_valid())
        self.assertIn(
            "Ya existe un recurso con este nombre.", form.errors["name"]
        )

    def test_clean_name_case_insensitive_duplicate(self):
        Resource.objects.create(name="Consultorio 1")
        form = ResourceForm(
            data={**self.valid_data, "name": "consultorio 1"}
        )
        self.assertFalse(form.is_valid())
        self.assertIn(
            "Ya existe un recurso con este nombre.", form.errors["name"]
        )

    def test_clean_name_excludes_self_on_update(self):
        resource = Resource.objects.create(name="Consultorio 1")
        form = ResourceForm(
            data={**self.valid_data, "name": "Consultorio 1"},
            instance=resource,
        )
        self.assertTrue(form.is_valid())

    def test_clean_name_allows_different_name(self):
        Resource.objects.create(name="Consultorio 1")
        form = ResourceForm(
            data={**self.valid_data, "name": "Consultorio 2"}
        )
        self.assertTrue(form.is_valid())

    def test_clean_name_empty_returns_none(self):
        """clean_name returns early if name is empty, letting required validation fire."""
        form = ResourceForm(data={**self.valid_data, "name": ""})
        # Form won't be valid due to required field, but clean_name should not crash
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)


# ── ResourceScheduleForm ───────────────────────────────────────────────────


class ResourceScheduleFormTest(TestCase):
    """Full overlap coverage (R15 — 7 scenarios) + start < end validation.

    NOTE: day_of_week=0 (Monday) is falsy in Python, so the form's
    ``if day:`` check in clean() skips overlap detection for Monday.
    All overlap tests use day_of_week=1 (Tuesday) to work around this.
    See bug note in return summary.
    """

    def setUp(self):
        self.resource = _create_resource(name="Consultorio 1")
        # Existing schedule: Tuesday (1) 09:00–12:00
        self.existing = ResourceSchedule.objects.create(
            resource=self.resource,
            day_of_week=1,
            start_time=time(9, 0),
            end_time=time(12, 0),
            slot_duration=30,
            max_appointments_per_slot=2,
        )

    def _data(self, **overrides):
        """Return form data as strings (simulating HTTP POST)."""
        data = {
            "day_of_week": 1,
            "start_time": "10:00",
            "end_time": "11:00",
            "slot_duration": 30,
            "max_appointments_per_slot": 1,
        }
        data.update(overrides)
        return data

    # ── start < end validation ──────────────────────────────────────────

    def test_start_equal_end_invalid(self):
        form = ResourceScheduleForm(
            data=self._data(start_time="09:00", end_time="09:00"),
            resource=self.resource,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("anterior", str(form.errors).lower())

    def test_start_after_end_invalid(self):
        form = ResourceScheduleForm(
            data=self._data(start_time="14:00", end_time="13:00"),
            resource=self.resource,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("anterior", str(form.errors).lower())

    def test_start_before_end_valid(self):
        form = ResourceScheduleForm(
            data=self._data(
                start_time="08:00",
                end_time="09:00",
                day_of_week=2,
            ),
            resource=self.resource,
        )
        self.assertTrue(form.is_valid())

    # ── Overlap: partial at start ────────────────────────────────────────

    def test_overlap_partial_start(self):
        """New 08:00–10:00 overlaps with existing 09:00–12:00 at the start."""
        form = ResourceScheduleForm(
            data=self._data(start_time="08:00", end_time="10:00"),
            resource=self.resource,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("superpone", str(form.errors).lower())

    # ── Overlap: partial at end ──────────────────────────────────────────

    def test_overlap_partial_end(self):
        """New 11:00–13:00 overlaps with existing 09:00–12:00 at the end."""
        form = ResourceScheduleForm(
            data=self._data(start_time="11:00", end_time="13:00"),
            resource=self.resource,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("superpone", str(form.errors).lower())

    # ── Overlap: new fully contained within existing ─────────────────────

    def test_overlap_new_inside_existing(self):
        """New 10:00–11:00 is completely inside existing 09:00–12:00."""
        form = ResourceScheduleForm(
            data=self._data(),
            resource=self.resource,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("superpone", str(form.errors).lower())

    # ── Overlap: existing fully contained within new ─────────────────────

    def test_overlap_existing_inside_new(self):
        """New 08:00–13:00 completely contains existing 09:00–12:00."""
        form = ResourceScheduleForm(
            data=self._data(start_time="08:00", end_time="13:00"),
            resource=self.resource,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("superpone", str(form.errors).lower())

    # ── Overlap: exact match ─────────────────────────────────────────────

    def test_overlap_exact_match(self):
        """New 09:00–12:00 exactly matches existing."""
        form = ResourceScheduleForm(
            data=self._data(start_time="09:00", end_time="12:00"),
            resource=self.resource,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("superpone", str(form.errors).lower())

    # ── Adjacent: end equals start (NOT overlap) ─────────────────────────

    def test_adjacent_end_equals_start_is_valid(self):
        """New 12:00–15:00 is adjacent (end=start) — NOT overlap."""
        form = ResourceScheduleForm(
            data=self._data(start_time="12:00", end_time="15:00"),
            resource=self.resource,
        )
        self.assertTrue(form.is_valid())

    # ── Non-adjacent non-overlapping ─────────────────────────────────────

    def test_non_overlapping_gap_is_valid(self):
        """New 13:00–15:00 has a gap after existing — NOT overlap."""
        form = ResourceScheduleForm(
            data=self._data(start_time="13:00", end_time="15:00"),
            resource=self.resource,
        )
        self.assertTrue(form.is_valid())

    # ── Different day is NOT overlap ─────────────────────────────────────

    def test_different_day_is_valid(self):
        """Same time on different day (Wednesday) — NOT overlap."""
        form = ResourceScheduleForm(
            data=self._data(day_of_week=2),
            resource=self.resource,
        )
        self.assertTrue(form.is_valid())

    # ── Different resource is NOT overlap ────────────────────────────────

    def test_different_resource_is_valid(self):
        """Same time, same day but different resource — NOT overlap."""
        other = _create_resource(name="Consultorio 2")
        form = ResourceScheduleForm(
            data=self._data(),
            resource=other,
        )
        self.assertTrue(form.is_valid())

    # ── Bug: day_of_week=0 (Monday) is falsy → overlap not detected ─────

    def test_monday_overlap_is_detected(self):
        """day_of_week=0 (Lunes) ya no es falsy — overlap se detecta correctamente."""
        monday_resource = _create_resource(name="Consultorio Monday")
        ResourceSchedule.objects.create(
            resource=monday_resource,
            day_of_week=0,
            start_time=time(9, 0),
            end_time=time(12, 0),
            slot_duration=30,
        )
        form = ResourceScheduleForm(
            data={
                "day_of_week": 0,
                "start_time": "10:00",
                "end_time": "11:00",
                "slot_duration": 30,
                "max_appointments_per_slot": 1,
            },
            resource=monday_resource,
        )
        # B1 fixed: `if day:` → `if day is not None:` — ahora detecta overlap
        self.assertFalse(form.is_valid())
        self.assertIn("El horario se superpone", str(form.errors))


# ── NonWorkingDayForm ──────────────────────────────────────────────────────


class NonWorkingDayFormTest(TestCase):
    """NonWorkingDayForm: past-date rejection, duplicate detection.

    NOTE: clean_date() accesses self.cleaned_data.get("is_recurring", False),
    but ``date`` is the first field — ``is_recurring`` hasn't been cleaned yet
    when clean_date runs. So ``is_recurring`` in clean_date always defaults to
    False. This means recurring past dates are also rejected. See bug note
    in return summary.
    """

    def setUp(self):
        self.valid_data = {
            "date": "2024-12-25",
            "reason": "Navidad",
            "is_recurring": True,
        }

    @patch("apps.resources.forms.timezone.localdate", return_value=date(2024, 11, 1))
    def test_recurring_past_date_is_valid(self, _mock_localdate):
        """Recurring past dates son válidas (feriados fijos como 15 de junio).
        B2 fixed: validación movida de clean_date() a clean() donde is_recurring
        ya está disponible en cleaned_data."""
        form = NonWorkingDayForm(
            data={
                "date": "2023-06-15",
                "reason": "Feriado patrio",
                "is_recurring": True,
            }
        )
        self.assertTrue(form.is_valid())

    @patch("apps.resources.forms.timezone.localdate", return_value=date(2024, 11, 1))
    def test_non_recurring_past_date_invalid(self, _mock_localdate):
        """Non-recurring days with past dates should be rejected."""
        form = NonWorkingDayForm(
            data={
                "date": "2023-06-15",
                "reason": "Feriado viejo",
                "is_recurring": False,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("anterior", str(form.errors.get("date", "")).lower())

    @patch("apps.resources.forms.timezone.localdate", return_value=date(2024, 11, 1))
    def test_future_date_valid(self, _mock_localdate):
        """Future dates are valid."""
        form = NonWorkingDayForm(data=self.valid_data)
        self.assertTrue(form.is_valid())

    @patch("apps.resources.forms.timezone.localdate", return_value=date(2024, 11, 1))
    def test_duplicate_date_invalid(self, _mock_localdate):
        """Creating a NonWorkingDay with an already-existing date is rejected."""
        NonWorkingDay.objects.create(date=date(2024, 12, 25), reason="Navidad")
        form = NonWorkingDayForm(data=self.valid_data)
        self.assertFalse(form.is_valid())
        self.assertIn("Ya existe", str(form.errors.get("date", "")))

    def test_empty_date_returns_none(self):
        """clean_date returns early if date is None, letting required validation fire."""
        form = NonWorkingDayForm(
            data={
                "date": "",
                "reason": "Test",
                "is_recurring": False,
            }
        )
        self.assertFalse(form.is_valid())
        # The date field is required, so it should have a required error
        self.assertIn("date", form.errors)

    @patch("apps.resources.forms.timezone.localdate", return_value=date(2024, 11, 1))
    def test_form_saves_successfully(self, _mock_localdate):
        """Happy path — form saves a NonWorkingDay correctly."""
        form = NonWorkingDayForm(
            data={
                "date": "2025-05-01",
                "reason": "Día del Trabajador",
                "is_recurring": True,
            }
        )
        self.assertTrue(form.is_valid())
        instance = form.save()
        self.assertEqual(instance.reason, "Día del Trabajador")
        self.assertTrue(instance.is_recurring)
        self.assertTrue(instance.is_active)
