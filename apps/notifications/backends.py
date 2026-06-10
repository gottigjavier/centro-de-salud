"""Notification backends — abstract base and concrete implementations."""
from abc import ABC, abstractmethod


class BaseNotificationBackend(ABC):
    """Abstract interface for notification delivery backends."""

    @abstractmethod
    def send(self, to: str, subject: str, body_html: str, body_plain: str,
             context: dict | None = None) -> tuple[bool, str]:
        """Send a notification. Returns (success: bool, error_message: str)."""
        ...


class EmailBackend(BaseNotificationBackend):
    """Send notifications via Django's email framework."""

    def send(self, to, subject, body_html, body_plain, context=None):
        from django.conf import settings
        from django.core.mail import EmailMultiAlternatives

        try:
            msg = EmailMultiAlternatives(
                subject, body_plain, settings.DEFAULT_FROM_EMAIL, [to],
            )
            msg.attach_alternative(body_html, "text/html")
            msg.send(fail_silently=False)
            return (True, "")
        except Exception as e:
            return (False, str(e))
