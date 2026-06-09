"""Resource models — consultorios, enfermerías, salas, etc."""
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import ActiveMixin, TimeStampedMixin

# ── Shared constants ──────────────────────────────────────────────────

DAYS_OF_WEEK = [
    (0, "Lunes"),
    (1, "Martes"),
    (2, "Miércoles"),
    (3, "Jueves"),
    (4, "Viernes"),
    (5, "Sábado"),
    (6, "Domingo"),
]


class NonWorkingDay(TimeStampedMixin, models.Model):
    """Días no laborables — feriados, días administrativos, etc."""

    date = models.DateField(unique=True, verbose_name="fecha")
    reason = models.CharField(max_length=200, verbose_name="motivo")
    is_recurring = models.BooleanField(
        default=False,
        verbose_name="recurrente",
        help_text="Si es un feriado fijo (ej: 25/12, 1/1) que se repite cada año",
    )
    is_active = models.BooleanField(default=True, verbose_name="activo")

    class Meta:
        verbose_name = "día no laborable"
        verbose_name_plural = "días no laborables"
        ordering = ["date"]

    def __str__(self):
        return f"{self.date} — {self.reason}"

    def clean(self):
        if not self.date:
            raise ValidationError({"date": "La fecha es obligatoria."})


class ResourceType(models.TextChoices):
    OFFICE = "office", "Consultorio"
    NURSERY = "nursery", "Enfermería"
    PROCEDURE = "procedure", "Sala de procedimientos"
    LAB = "lab", "Laboratorio"
    OTHER = "other", "Otro"


class Resource(TimeStampedMixin, ActiveMixin, models.Model):
    """A physical or virtual resource (consultorio, sala, etc.)."""

    name = models.CharField(max_length=100, verbose_name="nombre")
    type = models.CharField(
        max_length=20,
        choices=ResourceType.choices,
        default=ResourceType.OFFICE,
        verbose_name="tipo",
    )
    location = models.CharField(
        max_length=200, blank=True, verbose_name="ubicación"
    )
    max_capacity = models.PositiveIntegerField(
        default=1, verbose_name="capacidad máxima"
    )
    description = models.TextField(blank=True, verbose_name="descripción")

    class Meta:
        verbose_name = "recurso"
        verbose_name_plural = "recursos"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.get_type_display()})"


class ResourceSchedule(TimeStampedMixin, models.Model):
    """
    Weekly availability for a resource.

    Each row is one day range with open/close time.
    Multiple rows per resource = multiple slots (e.g. Mon 8-12, Mon 14-18).
    """

    DAYS_OF_WEEK = DAYS_OF_WEEK  # referencia a constante de módulo

    resource = models.ForeignKey(
        Resource, on_delete=models.CASCADE, related_name="schedules"
    )
    day_of_week = models.IntegerField(choices=DAYS_OF_WEEK, verbose_name="día")
    start_time = models.TimeField(verbose_name="hora apertura")
    end_time = models.TimeField(verbose_name="hora cierre")
    slot_duration = models.PositiveIntegerField(
        default=30,
        help_text="Duración del turno en minutos",
        verbose_name="duración turno",
    )
    max_appointments_per_slot = models.PositiveIntegerField(
        default=1,
        verbose_name="turnos máximos por ventana",
        help_text="Cantidad máxima de turnos que pueden asignarse en esta misma ventana horaria",
    )
    is_active = models.BooleanField(default=True, verbose_name="activo")

    class Meta:
        verbose_name = "horario de recurso"
        verbose_name_plural = "horarios de recursos"
        ordering = ["resource", "day_of_week", "start_time"]

    def __str__(self):
        day = dict(self.DAYS_OF_WEEK)[self.day_of_week]
        return f"{self.resource.name} — {day} {self.start_time}-{self.end_time}"

    def get_slot_count(self):
        """Cantidad de slots disponibles en este horario."""
        from datetime import datetime, timedelta

        start = datetime.combine(datetime.today(), self.start_time)
        end = datetime.combine(datetime.today(), self.end_time)
        total_minutes = (end - start).seconds // 60
        return total_minutes // self.slot_duration

    def get_total_capacity(self):
        """Capacidad total = slots × turnos máximos por slot."""
        return self.get_slot_count() * self.max_appointments_per_slot
