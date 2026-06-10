"""Signal handlers for appointment lifecycle."""
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.appointments.models import Appointment, AppointmentStatus


@receiver(post_save, sender=Appointment)
def appointment_post_save(sender, instance, created, **kwargs):
    if created and instance.status == AppointmentStatus.SCHEDULED:
        transaction.on_commit(lambda: _send_confirmation(instance))


def _send_confirmation(appointment):
    from .services import send_confirmation

    send_confirmation(appointment)
