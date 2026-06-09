"""Formularios para recursos, horarios y días no laborables."""

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import DAYS_OF_WEEK, NonWorkingDay, Resource, ResourceSchedule


# ── Resource ────────────────────────────────────────────────────────────


class ResourceForm(forms.ModelForm):
    """Formulario para crear/editar un recurso."""

    class Meta:
        model = Resource
        fields = ["name", "type", "location", "max_capacity", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input"}),
            "type": forms.Select(attrs={"class": "form-input"}),
            "location": forms.TextInput(attrs={"class": "form-input"}),
            "max_capacity": forms.NumberInput(
                attrs={"class": "form-input", "min": 1}
            ),
            "description": forms.Textarea(
                attrs={"class": "form-input", "rows": 3}
            ),
        }

    def clean_name(self):
        """Validar que el nombre sea único (case insensitive)."""
        name = self.cleaned_data.get("name")
        if not name:
            return name

        qs = Resource.objects.filter(name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Ya existe un recurso con este nombre.")
        return name


# ── ResourceSchedule ────────────────────────────────────────────────────


class ResourceScheduleForm(forms.ModelForm):
    """Formulario para agregar horarios a un recurso (HTMX inline)."""

    class Meta:
        model = ResourceSchedule
        fields = [
            "day_of_week",
            "start_time",
            "end_time",
            "slot_duration",
            "max_appointments_per_slot",
        ]
        widgets = {
            "day_of_week": forms.Select(
                choices=DAYS_OF_WEEK, attrs={"class": "form-input"}
            ),
            "start_time": forms.TimeInput(
                attrs={"class": "form-input", "type": "time"}
            ),
            "end_time": forms.TimeInput(
                attrs={"class": "form-input", "type": "time"}
            ),
            "slot_duration": forms.NumberInput(
                attrs={"class": "form-input", "min": 1}
            ),
            "max_appointments_per_slot": forms.NumberInput(
                attrs={"class": "form-input", "min": 1}
            ),
        }

    def __init__(self, *args, **kwargs):
        self.resource = kwargs.pop("resource", None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_time")
        end = cleaned.get("end_time")
        day = cleaned.get("day_of_week")

        # Validar que end_time > start_time
        if start and end and start >= end:
            raise ValidationError(
                "La hora de apertura debe ser anterior a la hora de cierre."
            )

        # Validar solapamiento con horarios existentes del mismo resource+day
        if start and end and day and self.resource:
            qs = ResourceSchedule.objects.filter(
                resource=self.resource,
                day_of_week=day,
                is_active=True,
            )
            # Excluir self si estamos editando
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            for existing in qs:
                # Solapamiento: nuevo.start < existente.end AND nuevo.end > existente.start
                if start < existing.end_time and end > existing.start_time:
                    raise ValidationError(
                        "El horario se superpone con otro existente."
                    )

        return cleaned


# ── NonWorkingDay ───────────────────────────────────────────────────────


class NonWorkingDayForm(forms.ModelForm):
    """Formulario para crear días no laborables."""

    class Meta:
        model = NonWorkingDay
        fields = ["date", "reason", "is_recurring"]
        widgets = {
            "date": forms.DateInput(
                attrs={"class": "form-input", "type": "date"}
            ),
            "reason": forms.TextInput(attrs={"class": "form-input"}),
            "is_recurring": forms.CheckboxInput(
                attrs={"class": "form-checkbox"}
            ),
        }

    def clean_date(self):
        date = self.cleaned_data.get("date")
        if not date:
            return date

        is_recurring = self.cleaned_data.get("is_recurring", False)

        # Validar que la fecha no sea pasada (solo para no recurrentes)
        if not is_recurring and date < timezone.localdate():
            raise forms.ValidationError(
                "La fecha no puede ser anterior a hoy."
            )

        # Validar unicidad de fecha (el modelo ya tiene unique=True,
        # pero este mensaje es más claro)
        if NonWorkingDay.objects.filter(date=date).exists():
            raise forms.ValidationError(
                "Ya existe un día no laborable registrado para esta fecha."
            )

        return date
