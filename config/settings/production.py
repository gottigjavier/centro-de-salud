"""Production settings for Vercel/Neon deployment.

Usage:
    DJANGO_SETTINGS_MODULE=config.settings.production

This file overrides base.py with production-safe values:
    - Forces SSL/HTTPS
    - Uses dj-database-url for PostgreSQL (Neon-ready)
    - Removes debug_toolbar
    - Configures email via SMTP
    - Adds structured logging
"""
from decouple import Csv, config

from .base import *  # noqa: F401, F403 — import everything from base

import dj_database_url  # noqa: F811 — re-import after wildcard

# ── Debug ────────────────────────────────────────────────────────────────────
DEBUG = False

# ── Security ─────────────────────────────────────────────────────────────────
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=True, cast=bool)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=31536000, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# ── Hosts ────────────────────────────────────────────────────────────────────
ALLOWED_HOSTS = config(
    "DJANGO_ALLOWED_HOSTS",
    default=".vercel.app,.now.sh,localhost,127.0.0.1,centro-de-salud.vercel.app/",
    cast=Csv(),
)

# ── Database ─────────────────────────────────────────────────────────────────
# Neon connection string examples:
#   Direct:     postgresql://user:pass@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require
#   Pooled:     postgresql://user:pass@ep-xxx-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require
#
# IMPORTANTE: Usá la pooled connection string de Neon para serverless,
# así no saturás las conexiones. El pooler usa PgBouncer en modo transaction.
#
# conn_max_age=0 porque en serverless no hay conexiones persistentes útiles.
# Con transaction pooling de Neon, cada request debe devolver la conexión
# al pool inmediatamente.
#
# NOTA: dj_database_url.config() ya lee DATABASE_URL del environment.
# No necesita default porque en producción DEBE estar configurada.
# Si no hay DATABASE_URL, db_config es {} y mantenemos lo que venga de base.py.
db_config = dj_database_url.config(
    conn_max_age=0,
    ssl_require=True,
)
if db_config:
    DATABASES["default"] = db_config

# ── Static files (Whitenoise) ────────────────────────────────────────────────
# Ya configurado en base.py con CompressedManifestStaticFilesStorage.
# collectstatic se ejecuta durante el build de Vercel.

# ── Remove debug_toolbar ─────────────────────────────────────────────────────
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != "debug_toolbar"]
MIDDLEWARE = [mw for mw in MIDDLEWARE if "debug_toolbar" not in mw]

# ── Email ────────────────────────────────────────────────────────────────────
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = config("EMAIL_HOST", default="")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
DEFAULT_FROM_EMAIL = config(
    "DEFAULT_FROM_EMAIL", default="noreply@centrodesalud.com"
)

# ── Logging ──────────────────────────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}
