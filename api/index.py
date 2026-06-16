"""
Vercel serverless entry point for Django.

Vercel's Python runtime looks for a WSGI callable named ``app``.
This module bootstraps Django with production settings and exposes
the WSGI application.

Why a separate index.py instead of reusing config/wsgi.py?
    - Vercel needs the handler at a predictable path (api/index.py).
    - We set DJANGO_SETTINGS_MODULE explicitly to production so both
      ASGI and WSGI entry points are decoupled from Vercel internals.
"""
import os

# Must be set BEFORE any Django import — Vercel may cache the module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

from django.core.wsgi import get_wsgi_application  # noqa: E402

app = get_wsgi_application()
