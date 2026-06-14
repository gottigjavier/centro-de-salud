"""Formularios para turnos — creación, edición y cancelación."""
from datetime import datetime

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Appointment, AppointmentStatus

INPUT_CLASS = "form-input w-full dark:bg-gray-700 dark:text-gray-100 dark:border-gray-600"


class AppointmentForm(forms.ModelForm):
    """Formulario para crear/editar un turno con selects dinámicos HTMX."""

    class Meta:
        model = Appointment
        fields = [
            "resource", "date", "professional", "start_time", "end_time",
            "patient_name", "patient_dni", "patient_phone", "patient_email",
            "send_reminder", "comments", "status",
        ]
        widgets = {
            "start_time": forms.HiddenInput(),
            "end_time": forms.HiddenInput(),
            "status": forms.HiddenInput(),
            "date": forms.DateInput(attrs={"type": "date", "class": INPUT_CLASS}),
            "patient_name": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "patient_dni": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "patient_phone": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "patient_email": forms.EmailInput(attrs={"class": INPUT_CLASS}),
            "send_reminder": forms.CheckboxInput(
                attrs={"class": "form-checkbox dark:bg-gray-700 dark:border-gray-600"}
            ),
            "comments": forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3}),
            "resource": forms.Select(attrs={"class": INPUT_CLASS}),
        }

    def __init__(self, *args, for_update=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.for_update = for_update

        # Professional empieza vacío en GET (se llena vía HTMX).
        # En POST usamos el queryset completo para que valide el valor enviado.
        if not self.is_bound:
            self.fields["professional"].queryset = self.fields["professional"].queryset.none()
        self.fields["professional"].widget.attrs["class"] = INPUT_CLASS

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
        if not phone or not phone.strip():
            raise forms.ValidationError("El teléfono de contacto es obligatorio.")
        return phone.strip()


    def clean(self):
        cleaned = super().clean()

        if self.for_update:
            return cleaned  # No validar solapamiento ni fechas en edición

        start_time = cleaned.get("start_time")
        end_time = cleaned.get("end_time")
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

        return cleaned


class CancelAppointmentForm(forms.Form):
    """Formulario para cancelar un turno con motivo obligatorio."""

    reason = forms.CharField(
        label="Motivo de cancelación",
        widget=forms.Textarea(attrs={
            "class": INPUT_CLASS,
            "rows": 3,
            "placeholder": "Indicá el motivo de la cancelación...",
        }),
        required=True,
        max_length=500,
    )
