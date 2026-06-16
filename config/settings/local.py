"""Local development settings — overrides base.py."""
from decouple import Csv, config

from .base import *  # noqa: F401, F403

# DEBUG=True para servir estáticos en desarrollo. Vercel usa production.py.
DEBUG = True

INSTALLED_APPS += ["debug_toolbar"]  # noqa: F405
MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")  # noqa: F405
INTERNAL_IPS = ["127.0.0.1", "localhost"]

# Los dominios de Vercel se aceptan por las dudas de que el entorno se
# confunda, pero local.py NO se usa nunca en el deploy (api/index.py y
# vercel_build.sh usan config.settings.production explícitamente).
ALLOWED_HOSTS = config(
    "DJANGO_ALLOWED_HOSTS",
    default="localhost,127.0.0.1,.vercel.app,.now.sh",
    cast=Csv(),
)

# Use SQLite for fast local dev (override with DATABASE_URL if you need PG)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "dev.db",  # noqa: F405
    }
}

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
