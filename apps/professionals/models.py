"""Professional models — médicos, enfermeros, etc."""
from django.conf import settings
from django.db import models

from apps.core.models import ActiveMixin, TimeStampedMixin
from apps.resources.models import DAYS_OF_WEEK, Resource


class Specialty(models.TextChoices):
    GENERAL = "general", "Medicina General"
    CARDIOLOGY = "cardiology", "Cardiología"
    PEDIATRICS = "pediatrics", "Pediatría"
    DERMATOLOGY = "dermatology", "Dermatología"
    TRAUMATOLOGY = "traumatology", "Traumatología"
    NURSING = "nursing", "Enfermería"
    OTHER = "other", "Otro"


class Professional(TimeStampedMixin, ActiveMixin, models.Model):
    """A healthcare professional who can be assigned to appointments."""

    first_name = models.CharField(max_length=100, verbose_name="nombre")
    last_name = models.CharField(max_length=100, verbose_name="apellido")
    specialty = models.CharField(
        max_length=30,
        choices=Specialty.choices,
        default=Specialty.GENERAL,
        verbose_name="especialidad",
    )
    license_number = models.CharField(
        max_length=50, unique=True, verbose_name="matrícula"
    )
    email = models.EmailField(blank=True, verbose_name="email")
    phone = models.CharField(
        max_length=20, blank=True, verbose_name="teléfono"
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="usuario del sistema",
        help_text="Usuario del sistema asociado a este profesional para autenticación y scoping",
    )
    resources = models.ManyToManyField(
        Resource,
        blank=True,
        related_name="professionals",
        verbose_name="recursos asignados",
        help_text="Recursos donde este profesional puede atender",
    )

    @property
    def name(self):
        """Nombre completo formateado: Apellido, Nombre."""
        return f"{self.last_name}, {self.first_name}"

    class Meta:
        verbose_name = "profesional"
        verbose_name_plural = "profesionales"
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.last_name}, {self.first_name} ({self.get_specialty_display()})"


class ProfessionalResourceAssignment(TimeStampedMixin, models.Model):
    """
    Asignación de un profesional a un recurso por período.

    Permite modelar: "el Dr. Pérez usa el Consultorio 1 los lunes y miércoles
    de 8 a 12hs, desde el 01/06/2026 hasta el 31/12/2026".
    """

    professional = models.ForeignKey(
        Professional,
        on_delete=models.CASCADE,
        related_name="assignments",
        verbose_name="profesional",
    )
    resource = models.ForeignKey(
        Resource,
        on_delete=models.CASCADE,
        related_name="assignments",
        verbose_name="recurso",
    )
    day_of_week = models.IntegerField(
        choices=DAYS_OF_WEEK,
        null=True,
        blank=True,
        verbose_name="día de semana",
        help_text="Si se deja vacío, aplica a todos los días",
    )
    start_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="fecha inicio",
        help_text="Si se deja vacío, la asignación es indefinida (vigente desde ahora)",
    )
    end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="fecha fin",
        help_text="Si se deja vacío, la asignación no tiene fecha de fin",
    )
    start_time = models.TimeField(verbose_name="hora inicio")
    end_time = models.TimeField(verbose_name="hora fin")
    is_active = models.BooleanField(default=True, verbose_name="activo")

    class Meta:
        verbose_name = "asignación profesional-recurso"
        verbose_name_plural = "asignaciones profesional-recurso"
        ordering = ["professional", "resource", "day_of_week", "start_time"]
        constraints = [
            models.UniqueConstraint(
                fields=["professional", "resource", "day_of_week", "start_time", "end_time"],
                name="unique_professional_resource_slot",
            )
        ]

    def __str__(self):
        days = dict(DAYS_OF_WEEK)
        day_str = days.get(self.day_of_week, "Todos los días")
        return (
            f"{self.professional} → {self.resource} "
            f"({day_str} {self.start_time}-{self.end_time})"
        )

    def clean(self):
        """Validar que end_date >= start_date y start_time < end_time."""
        from django.core.exceptions import ValidationError

        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({
                "end_date": "La fecha de fin no puede ser anterior a la fecha de inicio.",
            })
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError({
                "end_time": "La hora de fin debe ser posterior a la hora de inicio.",
            })

    def covers_date(self, date):
        """Verifica si una fecha específica está cubierta por esta asignación."""
        # Si hay start_date y la fecha es anterior, no cubre
        if self.start_date and date < self.start_date:
            return False
        # Si hay end_date y la fecha es posterior, no cubre
        if self.end_date and date > self.end_date:
            return False
        # Si day_of_week no es None, verificar que coincida
        if self.day_of_week is not None and date.weekday() != self.day_of_week:
            return False
        return True

    def covers_datetime(self, dt):
        """Verifica si una fecha Y hora específica está cubierta."""
        if not self.covers_date(dt.date()):
            return False
        # Verificar hora
        if self.start_time and dt.time() < self.start_time:
            return False
        if self.end_time and dt.time() >= self.end_time:
            return False
        return True

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
