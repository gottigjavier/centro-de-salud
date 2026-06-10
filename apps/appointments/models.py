"""Appointment models — turnos, patient data, scheduling."""
from datetime import datetime, date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedMixin
from apps.professionals.models import Professional
from apps.resources.models import Resource, ResourceSchedule


class AppointmentStatus(models.TextChoices):
    SCHEDULED = "scheduled", "Programado"
    CONFIRMED = "confirmed", "Confirmado"
    ARRIVED = "arrived", "Llegó"
    IN_PROGRESS = "in_progress", "En atención"
    COMPLETED = "completed", "Completado"
    CANCELLED = "cancelled", "Cancelado"
    NO_SHOW = "no_show", "No asistió"


# Transiciones de estado válidas para Appointment
APPOINTMENT_VALID_TRANSITIONS = {
    AppointmentStatus.SCHEDULED: [AppointmentStatus.CONFIRMED, AppointmentStatus.CANCELLED],
    AppointmentStatus.CONFIRMED: [AppointmentStatus.ARRIVED, AppointmentStatus.CANCELLED],
    AppointmentStatus.ARRIVED: [AppointmentStatus.IN_PROGRESS, AppointmentStatus.CANCELLED],
    AppointmentStatus.IN_PROGRESS: [AppointmentStatus.COMPLETED],
    AppointmentStatus.COMPLETED: [],  # Terminal
    AppointmentStatus.CANCELLED: [],  # Terminal
    AppointmentStatus.NO_SHOW: [],   # Terminal
}


class AppointmentManager(models.Manager):
    """Default manager: excludes soft-deleted records."""

    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class Appointment(TimeStampedMixin, models.Model):
    """
    A patient appointment/turno.

    Links patient info with a resource, professional, date, and time slot.
    """

    # Patient data (denormalized for quick access)
    patient_name = models.CharField(
        max_length=200, verbose_name="nombre del paciente"
    )
    patient_dni = models.CharField(
        max_length=20, verbose_name="DNI del paciente"
    )
    patient_phone = models.CharField(
        max_length=20, blank=True, default="", verbose_name="teléfono de contacto"
    )
    patient_email = models.EmailField(
        blank=True, verbose_name="email de contacto"
    )
    send_reminder = models.BooleanField(
        default=False, verbose_name="enviar recordatorio",
        help_text="Enviar recordatorio automático antes del turno",
    )

    # Appointment data
    resource = models.ForeignKey(
        Resource,
        on_delete=models.PROTECT,
        related_name="appointments",
        verbose_name="recurso",
    )
    professional = models.ForeignKey(
        Professional,
        on_delete=models.PROTECT,
        related_name="appointments",
        verbose_name="profesional",
    )
    date = models.DateField(verbose_name="fecha")
    start_time = models.TimeField(verbose_name="hora inicio")
    end_time = models.TimeField(verbose_name="hora fin")
    status = models.CharField(
        max_length=20,
        choices=AppointmentStatus.choices,
        default=AppointmentStatus.SCHEDULED,
        verbose_name="estado",
    )

    # Metadata
    comments = models.TextField(
        blank=True, verbose_name="comentarios"
    )
    cancellation_reason = models.TextField(
        blank=True,
        default="",
        verbose_name="motivo de cancelación",
        help_text="Motivo obligatorio cuando se cancela el turno",
    )
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appointments_created",
        verbose_name="creado por",
    )

    # Soft-delete
    deleted_at = models.DateTimeField(
        null=True, blank=True, db_index=True, verbose_name="eliminado el",
    )

    objects = AppointmentManager()
    all_objects = models.Manager()

    # ── Model hooks ────────────────────────────────────────────────────

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        # Guardar estado original para detectar cambios en clean()
        instance._original_status = instance.status
        instance._original_date = instance.date
        instance._original_start_time = instance.start_time
        return instance

    # ── Validation ──────────────────────────────────────────────────────

    def _is_temporal_field_changed(self):
        """Detecta si date o start_time cambiaron (para auto-exclusión en updates)."""
        if not self.pk:
            return True  # Es creación, siempre validar
        try:
            old = Appointment.objects.get(pk=self.pk)
            return old.date != self.date or old.start_time != self.start_time
        except Appointment.DoesNotExist:
            return True

    def clean(self):
        """Validar reglas de negocio del turno."""
        errors = {}

        # ── Validación de transición de estado ──────────────────────────
        if self.pk and hasattr(self, '_original_status'):
            old_status = self._original_status
            new_status = self.status
            if old_status != new_status:
                allowed = APPOINTMENT_VALID_TRANSITIONS.get(old_status, [])
                if new_status not in allowed:
                    raise ValidationError({
                        "status": (
                            f"No se puede cambiar el estado de '{dict(AppointmentStatus.choices)[old_status]}' "
                            f"a '{dict(AppointmentStatus.choices)[new_status]}'. "
                            f"Transiciones permitidas desde '{dict(AppointmentStatus.choices)[old_status]}': "
                            f"{', '.join(dict(AppointmentStatus.choices)[s] for s in allowed) or 'ninguna'}."
                        )
                    })

        # ── V-001: No turnos en pasado ──────────────────────────────────
        if self.date and self.start_time:
            appointment_dt = timezone.make_aware(
                datetime.combine(self.date, self.start_time),
                timezone.get_current_timezone(),
            )
            if appointment_dt < timezone.now():
                # Auto-exclusión si es update y no cambiaron date/start_time
                if (
                    self.pk
                    and hasattr(self, '_original_date')
                    and hasattr(self, '_original_start_time')
                    and self._original_date == self.date
                    and self._original_start_time == self.start_time
                ):
                    pass  # Update sin cambio temporal - permitir
                else:
                    errors["start_time"] = "No se pueden crear turnos en el pasado."

        # Si faltan campos esenciales (resource, date, prof, time), salimos
        # Usamos _id para FK para evitar RelatedObjectDoesNotExist al acceder
        if not self.resource_id or not self.date:
            if errors:
                raise ValidationError(errors)
            return

        # V-002: Recurso habilitado ese día
        schedules = ResourceSchedule.objects.filter(
            resource=self.resource,
            day_of_week=self.date.weekday(),
            is_active=True,
        )
        if not schedules.exists():
            errors["date"] = "El recurso no está habilitado para este día."

        if errors:
            raise ValidationError(errors)

        # V-003 + V-004: Horario dentro del rango y duración correcta
        if self.start_time and self.end_time:
            matching_schedule = None
            for schedule in schedules:
                if schedule.start_time <= self.start_time and self.end_time <= schedule.end_time:
                    matching_schedule = schedule
                    break

            if not matching_schedule:
                raise ValidationError(
                    "El horario del turno está fuera del horario habilitado del recurso."
                )

            # V-004: Duración == slot_duration
            turno_minutes = (
                datetime.combine(date.min, self.end_time)
                - datetime.combine(date.min, self.start_time)
            ).seconds // 60
            if turno_minutes != matching_schedule.slot_duration:
                raise ValidationError(
                    f"La duración del turno debe ser de {matching_schedule.slot_duration} minutos."
                )

            # Guardar para T-005 (V-006: capacidad contra max_appointments_per_slot)
            self._valid_schedule = matching_schedule

        # ── V-005: NonWorkingDay (día no laborable) ────────────────────
        from apps.resources.models import NonWorkingDay

        if NonWorkingDay.objects.filter(
            date=self.date, is_active=True
        ).exists():
            raise ValidationError(
                f"La fecha {self.date} es un día no laborable."
            )

        # ── V-006: Capacidad del slot ──────────────────────────────────
        if getattr(self, '_valid_schedule', None):
            current_count = Appointment.objects.filter(
                resource=self.resource,
                date=self.date,
                start_time=self.start_time,
            ).exclude(
                status__in=[
                    AppointmentStatus.CANCELLED,
                    AppointmentStatus.NO_SHOW,
                ]
            ).exclude(pk=self.pk).count()

            if current_count >= self._valid_schedule.max_appointments_per_slot:
                raise ValidationError(
                    f"El cupo máximo de {self._valid_schedule.max_appointments_per_slot} "
                    f"turno(s) para este horario ya fue alcanzado."
                )

        # ── V-007: Solapamiento con otros turnos ───────────────────────
        if self.start_time and self.end_time:
            overlaps = Appointment.objects.filter(
                resource=self.resource,
                date=self.date,
                start_time__lt=self.end_time,
                end_time__gt=self.start_time,
            ).exclude(
                status__in=[
                    AppointmentStatus.CANCELLED,
                    AppointmentStatus.NO_SHOW,
                ]
            ).exclude(pk=self.pk)

            if overlaps.exists():
                conflicting = overlaps.first()
                raise ValidationError(
                    f"El turno se superpone con otro turno existente: "
                    f"'{conflicting.patient_name}' de {conflicting.start_time} "
                    f"a {conflicting.end_time}."
                )

        # ── V-008: Profesional asignado al recurso ─────────────────────
        if (
            getattr(settings, "APPOINTMENT_VALIDATE_PROFESSIONAL_ASSIGNMENT", True)
            and self.professional_id
            and self.start_time
            and self.end_time
        ):
            from apps.professionals.models import ProfessionalResourceAssignment

            has_assignment = ProfessionalResourceAssignment.objects.filter(
                professional=self.professional,
                resource=self.resource,
                is_active=True,
                start_time__lte=self.start_time,
                end_time__gte=self.end_time,
            ).filter(
                models.Q(day_of_week__isnull=True)
                | models.Q(day_of_week=self.date.weekday())
            ).filter(
                models.Q(start_date__isnull=True)
                | models.Q(start_date__lte=self.date)
            ).filter(
                models.Q(end_date__isnull=True)
                | models.Q(end_date__gte=self.date)
            ).exists()

            if not has_assignment:
                raise ValidationError(
                    f"El profesional '{self.professional}' no está asignado "
                    f"al recurso '{self.resource}' para la fecha y horario "
                    f"solicitados."
                )

    class Meta:
        verbose_name = "turno"
        verbose_name_plural = "turnos"
        ordering = ["date", "start_time"]
        base_manager_name = "all_objects"
        indexes = [
            models.Index(fields=["date", "resource"]),
            models.Index(fields=["date", "professional"]),
            models.Index(fields=["resource", "date", "start_time"]),
            models.Index(fields=["resource", "date", "status"]),
            models.Index(fields=["patient_dni"]),
            models.Index(fields=["status"]),
            models.Index(
                fields=["send_reminder", "status", "date", "start_time"],
                name="idx_send_reminder_candidates",
            ),
        ]

    def __str__(self):
        return (
            f"{self.patient_name} — {self.date} {self.start_time}-{self.end_time} "
            f"({self.get_status_display()})"
        )
