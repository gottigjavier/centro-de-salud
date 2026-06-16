"""ASGI config for turnero project.

Detects serverless/production environments automatically.
Priority: 1) DJANGO_SETTINGS_MODULE already set, 2) serverless indicators,
3) fall back to local dev settings.

Serverless indicators (any of these → production):
  - VERCEL, VERCEL_ENV       (Vercel system env vars)
  - AWS_LAMBDA_FUNCTION_NAME  (AWS Lambda — Vercel runs on top of it)
  - DATABASE_URL               (explicitly set in Vercel Dashboard)
"""
import os

from django.core.asgi import get_asgi_application


def _running_on_serverless() -> bool:
    """True if we detect a serverless / Vercel environment."""
    return any(
        [
            os.environ.get("VERCEL"),
            os.environ.get("VERCEL_ENV"),
            os.environ.get("AWS_LAMBDA_FUNCTION_NAME"),
            os.environ.get("DATABASE_URL"),
        ]
    )


if _running_on_serverless() or os.environ.get("DATABASE_URL"):
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.production"
else:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

application = get_asgi_application()
