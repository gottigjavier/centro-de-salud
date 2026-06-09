"""Formularios para profesionales y asignaciones."""
from django import forms
from django.core.exceptions import ValidationError

from .models import DAYS_OF_WEEK, Professional, ProfessionalResourceAssignment


# ── Professional ────────────────────────────────────────────────────────


class ProfessionalForm(forms.ModelForm):
    """Formulario para crear/editar un profesional."""

    class Meta:
        model = Professional
        fields = [
            "first_name",
            "last_name",
            "specialty",
            "license_number",
            "email",
            "phone",
            "resources",
        ]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-input"}),
            "last_name": forms.TextInput(attrs={"class": "form-input"}),
            "specialty": forms.Select(attrs={"class": "form-input"}),
            "license_number": forms.TextInput(attrs={"class": "form-input"}),
            "email": forms.EmailInput(attrs={"class": "form-input"}),
            "phone": forms.TextInput(attrs={"class": "form-input"}),
            "resources": forms.SelectMultiple(attrs={"class": "form-input"}),
        }

    def clean_license_number(self):
        """Validar que la matrícula sea única (case insensitive)."""
        license_number = self.cleaned_data.get("license_number")
        if not license_number:
            return license_number

        qs = Professional.objects.filter(license_number__iexact=license_number)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(
                "Ya existe un profesional con esta matrícula."
            )
        return license_number


# ── ProfessionalResourceAssignment ──────────────────────────────────────


def _date_ranges_overlap(new_start, new_end, existing_start, existing_end):
    """Dos rangos de fechas se superponen. Null = infinito en esa dirección.

    Lógica:
    - Si ambos rangos tienen None en ambos extremos → indefinidos → solapan.
    - Si ambos rangos tienen todos los valores definidos → overlap estándar.
    - Si un rango es completamente indefinido (new=None/new_end=None)
      → solapa con cualquier rango existente.
    - Casos mixtos: un extremo definido, el otro no → el extremo definido
      actúa como límite, el null es infinito.
    """
    # Ambos nulos: indefinidos
    if (
        new_start is None and new_end is None
        and existing_start is None and existing_end is None
    ):
        return True
    # Ambos con valores: overlap estándar
    if (
        new_start is not None and new_end is not None
        and existing_start is not None and existing_end is not None
    ):
        return new_start < existing_end and new_end > existing_start
    # Un rango indefinido (ambos lados nulos): solapa con todo
    if new_start is None and new_end is None:
        return True
    if existing_start is None and existing_end is None:
        return True
    # Casos mixtos null/no-null
    if new_start is not None and new_end is None:
        if existing_start is not None and existing_end is not None:
            return existing_end > new_start
        return True
    if new_start is None and new_end is not None:
        if existing_start is not None and existing_end is not None:
            return existing_start < new_end
        return True
    if existing_start is not None and existing_end is None:
        if new_end is not None:
            return new_end > existing_start
        return True
    if existing_start is None and existing_end is not None:
        if new_start is not None:
            return new_start < existing_end
        return True
    return False


class ProfessionalResourceAssignmentForm(forms.ModelForm):
    """Formulario para agregar asignaciones a un profesional (HTMX inline)."""

    class Meta:
        model = ProfessionalResourceAssignment
        fields = [
            "resource",
            "day_of_week",
            "start_date",
            "end_date",
            "start_time",
            "end_time",
        ]
        widgets = {
            "resource": forms.Select(attrs={"class": "form-input"}),
            "day_of_week": forms.Select(
                choices=DAYS_OF_WEEK, attrs={"class": "form-input"}
            ),
            "start_date": forms.DateInput(
                attrs={"class": "form-input", "type": "date"}
            ),
            "end_date": forms.DateInput(
                attrs={"class": "form-input", "type": "date"}
            ),
            "start_time": forms.TimeInput(
                attrs={"class": "form-input", "type": "time"}
            ),
            "end_time": forms.TimeInput(
                attrs={"class": "form-input", "type": "time"}
            ),
        }

    def __init__(self, *args, **kwargs):
        self.professional = kwargs.pop("professional", None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        resource = cleaned.get("resource")
        day = cleaned.get("day_of_week")
        start_date = cleaned.get("start_date")
        end_date = cleaned.get("end_date")
        start_time = cleaned.get("start_time")
        end_time = cleaned.get("end_time")

        # Validar que end_time > start_time
        if start_time and end_time and start_time >= end_time:
            raise ValidationError(
                "La hora de fin debe ser posterior a la hora de inicio."
            )

        # Validar que end_date >= start_date
        if start_date and end_date and end_date < start_date:
            raise ValidationError(
                "La fecha de fin no puede ser anterior a la fecha de inicio."
            )

        # Validar solapamiento
        if (
            self.professional and resource and start_time and end_time
            and self._has_overlap(
                self.professional, resource, day,
                start_date, end_date, start_time, end_time,
            )
        ):
            raise ValidationError(
                "El horario se superpone con una asignación existente."
            )

        return cleaned

    def _has_overlap(self, professional, resource, day,
                     start_date, end_date, start_time, end_time):
        """Verifica si existe una asignación activa que se superponga."""
        qs = ProfessionalResourceAssignment.objects.filter(
            professional=professional,
            resource=resource,
            is_active=True,
        )
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        for existing in qs:
            # Day of week overlap (null = all days)
            # NOTA: usamos `day is not None` (no `if day`) porque
            # day_of_week=0 (Lunes) es falsy en Python
            if (
                day is not None
                and existing.day_of_week is not None
                and day != existing.day_of_week
            ):
                continue
            # Time overlap
            if not (start_time < existing.end_time
                    and end_time > existing.start_time):
                continue
            # Date range overlap
            if not _date_ranges_overlap(
                start_date, end_date,
                existing.start_date, existing.end_date,
            ):
                continue
            return True
        return False
