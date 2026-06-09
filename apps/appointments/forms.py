"""Formularios para turnos — creación, edición y cancelación."""
from datetime import datetime

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Appointment, AppointmentStatus


class AppointmentForm(forms.ModelForm):
    """Formulario para crear/editar un turno con selects dinámicos HTMX."""

    class Meta:
        model = Appointment
        fields = [
            "resource", "date", "professional", "start_time", "end_time",
            "patient_name", "patient_dni", "patient_phone", "patient_email",
            "comments", "status",
        ]
        widgets = {
            "start_time": forms.HiddenInput(),
            "end_time": forms.HiddenInput(),
            "status": forms.HiddenInput(),
            "date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "patient_name": forms.TextInput(attrs={"class": "form-input"}),
            "patient_dni": forms.TextInput(attrs={"class": "form-input"}),
            "patient_phone": forms.TextInput(attrs={"class": "form-input"}),
            "patient_email": forms.EmailInput(attrs={"class": "form-input"}),
            "comments": forms.Textarea(attrs={"class": "form-input", "rows": 3}),
            "resource": forms.Select(attrs={"class": "form-input"}),
        }

    def __init__(self, *args, for_update=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.for_update = for_update

        # Professional empieza vacío en GET (se llena vía HTMX).
        # En POST usamos el queryset completo para que valide el valor enviado.
        if not self.is_bound:
            self.fields["professional"].queryset = self.fields["professional"].queryset.none()
        self.fields["professional"].widget.attrs["class"] = "form-input"

        # Status se setea programáticamente desde la view — no lo requiere del form
        self.fields["status"].required = False

        # patient_name y patient_dni tienen validación custom en clean_*()
        # que maneja el mensaje de error con mejor UX
        self.fields["patient_name"].required = False
        self.fields["patient_dni"].required = False

        if for_update:
            # En edición solo se editan datos del paciente
            for field_name in [
                "resource", "date", "professional",
                "start_time", "end_time", "status",
            ]:
                self.fields.pop(field_name, None)
        else:
            self.initial["status"] = AppointmentStatus.SCHEDULED

    def clean_patient_name(self):
        name = self.cleaned_data.get("patient_name")
        if not name or len(name.strip()) < 2:
            raise forms.ValidationError("El nombre del paciente debe tener al menos 2 caracteres.")
        return name.strip()

    def clean_patient_dni(self):
        dni = self.cleaned_data.get("patient_dni")
        if not dni:
            raise forms.ValidationError("El DNI del paciente es obligatorio.")
        return dni.strip()

    def clean_patient_phone(self):
        phone = self.cleaned_data.get("patient_phone")
        if phone:
            return phone.strip()
        return ""

    def clean(self):
        cleaned = super().clean()

        if self.for_update:
            return cleaned  # No validar solapamiento ni fechas en edición

        start_time = cleaned.get("start_time")
        end_time = cleaned.get("end_time")
        resource = cleaned.get("resource")
        professional = cleaned.get("professional")
        date = cleaned.get("date")

        # start_time < end_time
        if start_time and end_time and start_time >= end_time:
            raise ValidationError("La hora de inicio debe ser anterior a la hora de fin.")

        # Fecha futura para turnos nuevos
        if date and start_time:
            appointment_dt = timezone.make_aware(
                datetime.combine(date, start_time),
                timezone.get_current_timezone(),
            )
            if appointment_dt < timezone.now():
                self.add_error("start_time", "No se pueden crear turnos en el pasado.")

        # Solapamiento (V-007)
        if all([resource, professional, date, start_time, end_time]):
            self._validate_no_overlap(resource, professional, date, start_time, end_time)

        return cleaned

    def _validate_no_overlap(self, resource, professional, date, start_time, end_time):
        """Verifica que no haya solapamiento con turnos existentes."""
        qs = Appointment.objects.filter(
            resource=resource,
            professional=professional,
            date=date,
            start_time__lt=end_time,
            end_time__gt=start_time,
        ).exclude(
            status__in=[AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW],
        )
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError(
                "El turno se superpone con otro turno existente en ese horario."
            )


class CancelAppointmentForm(forms.Form):
    """Formulario para cancelar un turno con motivo obligatorio."""

    reason = forms.CharField(
        label="Motivo de cancelación",
        widget=forms.Textarea(attrs={
            "class": "form-input",
            "rows": 3,
            "placeholder": "Indicá el motivo de la cancelación...",
        }),
        required=True,
        max_length=500,
    )
