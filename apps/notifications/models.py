"""Notification models — config and logs."""
from django.db import models

from apps.core.models import TimeStampedMixin


class NotificationConfig(TimeStampedMixin, models.Model):
    """Per-resource or global notification settings."""

    resource = models.OneToOneField(
        "resources.Resource", on_delete=models.CASCADE,
        null=True, blank=True, verbose_name="recurso",
        help_text="Dejar vacío para configuración global por defecto",
    )
    reminder_enabled = models.BooleanField(
        default=True, verbose_name="recordatorios habilitados",
    )
    reminder_before_minutes = models.PositiveIntegerField(
        default=1440, verbose_name="recordar antes (minutos)",
        help_text="Minutos antes del turno para enviar el recordatorio",
    )
    email_enabled = models.BooleanField(
        default=True, verbose_name="email habilitado",
    )
    whatsapp_enabled = models.BooleanField(
        default=False, verbose_name="WhatsApp habilitado",
    )

    class Meta:
        verbose_name = "configuración de notificaciones"
        verbose_name_plural = "configuraciones de notificaciones"

    def __str__(self):
        if self.resource_id:
            return f"Notificaciones: {self.resource.name}"
        return "Notificaciones: Configuración global"


class NotificationLog(models.Model):
    """Audit log for every notification sent or attempted."""

    class Channel(models.TextChoices):
        EMAIL = "email", "Email"
        WHATSAPP = "whatsapp", "WhatsApp"

    class Type(models.TextChoices):
        CONFIRMATION = "confirmation", "Confirmación"
        REMINDER = "reminder", "Recordatorio"
        CANCELLATION = "cancellation", "Cancelación"

    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        SENT = "sent", "Enviado"
        FAILED = "failed", "Fallido"

    appointment = models.ForeignKey(
        "appointments.Appointment", on_delete=models.CASCADE,
        related_name="notification_logs", verbose_name="turno",
    )
    channel = models.CharField(
        max_length=20, choices=Channel.choices, verbose_name="canal",
    )
    notification_type = models.CharField(
        max_length=20, choices=Type.choices, verbose_name="tipo",
    )
    recipient = models.CharField(
        max_length=255, verbose_name="destinatario",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices,
        default=Status.PENDING, verbose_name="estado",
    )
    error_message = models.TextField(
        blank=True, default="", verbose_name="mensaje de error",
    )
    sent_at = models.DateTimeField(
        null=True, blank=True, verbose_name="enviado el",
    )
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name="creado el",
    )

    class Meta:
        verbose_name = "registro de notificación"
        verbose_name_plural = "registros de notificaciones"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["appointment", "notification_type"]),
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return (
            f"{self.get_channel_display()} "
            f"({self.get_notification_type_display()}) - {self.appointment_id}"
        )
