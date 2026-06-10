"""Tests for management commands — send_reminders (stub)."""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase


class SendRemindersCommandTest(TestCase):
    """Tests for the send_reminders management command."""

    def test_command_runs_successfully(self):
        """send_reminders sin argumentos → ejecuta y muestra mensaje stub."""
        out = StringIO()
        call_command("send_reminders", stdout=out)
        self.assertIn("no implementado", out.getvalue().lower())

    def test_command_with_dry_run(self):
        """send_reminders --dry-run → ejecuta y muestra mensaje stub."""
        out = StringIO()
        call_command("send_reminders", dry_run=True, stdout=out)
        self.assertIn("no implementado", out.getvalue().lower())
