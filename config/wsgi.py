"""WSGI config for turnero project.

Auto-detects Vercel environment and switches to production settings.
"""
import os

from django.core.wsgi import get_wsgi_application

if os.environ.get("VERCEL"):
    os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE", "config.settings.production"
    )
else:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

application = get_wsgi_application()
