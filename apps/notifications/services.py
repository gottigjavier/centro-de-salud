"""Notification service layer — business logic for sending notifications."""
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils.timezone import now

from .backends import EmailBackend
from .models import NotificationLog


def send_confirmation(appointment):
    """Send confirmation email for an appointment. Creates NotificationLog entry."""
    if not appointment.patient_email:
        return NotificationLog.objects.create(
            appointment=appointment,
            channel=NotificationLog.Channel.EMAIL,
            notification_type=NotificationLog.Type.CONFIRMATION,
            recipient=appointment.patient_phone or "—",
            status=NotificationLog.Status.FAILED,
            error_message="Paciente sin email",
        )

    backend = EmailBackend()
    context = {
        "appointment": appointment,
        "clinic_name": getattr(settings, "CLINIC_NAME", "Centro de Salud"),
        "clinic_address": getattr(settings, "CLINIC_ADDRESS", ""),
    }
    body_html = render_to_string(
        "notifications/emails/confirmation.html", context,
    )
    body_plain = strip_tags(body_html)

    try:
        success, error = backend.send(
            to=appointment.patient_email,
            subject=f"Turno confirmado - {appointment.date}",
            body_html=body_html,
            body_plain=body_plain,
            context=context,
        )
    except Exception as e:
        success, error = False, str(e)

    return NotificationLog.objects.create(
        appointment=appointment,
        channel=NotificationLog.Channel.EMAIL,
        notification_type=NotificationLog.Type.CONFIRMATION,
        recipient=appointment.patient_email,
        status=NotificationLog.Status.SENT if success else NotificationLog.Status.FAILED,
        error_message="" if success else error,
        sent_at=now() if success else None,
    )
