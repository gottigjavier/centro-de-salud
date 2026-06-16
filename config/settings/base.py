"""
Base Django settings for turnero project.

Overrides go in local.py (dev) or production.py (prod).
"""
import os
from pathlib import Path

from decouple import Csv, config

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ── Security ────────────────────────────────────────────────────────────────
SECRET_KEY = config("DJANGO_SECRET_KEY", default="insecure-dev-key-change-me")
DEBUG = config("DJANGO_DEBUG", default=True, cast=bool)
ALLOWED_HOSTS = config("DJANGO_ALLOWED_HOSTS", default="localhost,127.0.0.1,centro-de-salud.vercel.app", cast=Csv())

# ── Apps ────────────────────────────────────────────────────────────────────
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "django_htmx",
    "allauth",
    "allauth.account",
]

LOCAL_APPS = [
    "apps.core",
    "apps.accounts",
    "apps.resources",
    "apps.professionals",
    "apps.appointments",
    "apps.reports",
    "apps.notifications",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ── Middleware ──────────────────────────────────────────────────────────────
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.accounts.middleware.AdminSetupMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "config.urls"

# ── Templates ───────────────────────────────────────────────────────────────
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ── Database ────────────────────────────────────────────────────────────────
# Default: PostgreSQL via DATABASE_URL.
# Falls back to SQLite for local dev when DATABASE_URL is not set.
# Uses dj-database-url if available (recommended for production), otherwise
# falls back to simple regex parsing for basic PostgreSQL URLs.
try:
    import dj_database_url

    DATABASES = {
        "default": dj_database_url.config(
            default="sqlite:///" + str(BASE_DIR / "dev.db"),
            conn_max_age=600,
        )
    }
except ImportError:
    # Fallback when dj-database-url is not installed (e.g. fresh dev env)
    DATABASE_URL = config("DATABASE_URL", default=None)
    if DATABASE_URL:
        import re

        match = re.match(
            r"postgres(?:ql)?://(.+):(.+)@(.+):(\d+)/(.+)", DATABASE_URL
        )
        if match:
            user, password, host, port, name = match.groups()
            DATABASES = {
                "default": {
                    "ENGINE": "django.db.backends.postgresql",
                    "NAME": name,
                    "USER": user,
                    "PASSWORD": password,
                    "HOST": host,
                    "PORT": port,
                    "ATOMIC_REQUESTS": True,
                    "CONN_MAX_AGE": 600,
                }
            }
        else:
            DATABASES = {
                "default": {
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME": BASE_DIR / "dev.db",
                }
            }
    else:
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": BASE_DIR / "dev.db",
            }
        }

# ── Auth ────────────────────────────────────────────────────────────────────
AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "account_login"
LOGIN_REDIRECT_URL = "/agenda/"
LOGOUT_REDIRECT_URL = "account_login"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

# django-allauth
# Settings modernas (allauth >= 65)
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "optional"
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
# Settings legacy (allauth < 65.6) — necesarias para que los system checks
# de la versión 65.3.1 (usada en Docker) no tiren CRITICALs.
# Ver: https://github.com/pennersr/django-allauth/issues/4739
ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_EMAIL_REQUIRED = True
# ── Internationalization ────────────────────────────────────────────────────
LANGUAGE_CODE = "es-ar"
TIME_ZONE = "America/Argentina/Buenos_Aires"
USE_I18N = True
USE_TZ = True

# ── Appointment validation ────────────────────────────────────────────
APPOINTMENT_VALIDATE_PROFESSIONAL_ASSIGNMENT = True

# ── Static files ────────────────────────────────────────────────────────────
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# ── Media ───────────────────────────────────────────────────────────────────
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# ── Default primary key ─────────────────────────────────────────────────────
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── Notificaciones ────────────────────────────────────────────────────────────
CLINIC_NAME = "Centro de Salud"
CLINIC_ADDRESS = ""
