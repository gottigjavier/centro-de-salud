"""Tests for notification admin registration and permissions."""
from django.contrib.admin import site
from django.test import TestCase

from apps.notifications.models import NotificationConfig, NotificationLog
from apps.notifications.admin import NotificationConfigAdmin, NotificationLogAdmin


class NotificationAdminTest(TestCase):
    """Verify NotificationConfig and NotificationLog are registered in admin
    with correct permissions (log is read-only)."""

    def test_notification_config_registered(self):
        """T-NOT-025: NotificationConfig está registrado en el admin."""
        self.assertIn(NotificationConfig, site._registry)

    def test_notification_log_registered(self):
        """T-NOT-026: NotificationLog está registrado en el admin."""
        self.assertIn(NotificationLog, site._registry)

    def test_notification_log_no_add(self):
        """T-NOT-026: NotificationLogAdmin no permite agregar registros."""
        model_admin = site._registry[NotificationLog]
        self.assertFalse(model_admin.has_add_permission(None))

    def test_notification_log_no_change(self):
        """T-NOT-026: NotificationLogAdmin no permite editar registros."""
        model_admin = site._registry[NotificationLog]
        self.assertFalse(model_admin.has_change_permission(None, obj=None))
