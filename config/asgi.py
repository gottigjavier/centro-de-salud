"""ASGI config for turnero project.

Auto-detects Vercel environment and switches to production settings.
"""
import os

from django.core.asgi import get_asgi_application

if os.environ.get("VERCEL"):
    os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE", "config.settings.production"
    )
else:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

application = get_asgi_application()
