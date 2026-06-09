"""Test settings — extends local but removes debug_toolbar and sets staticfiles."""

from .base import *  # noqa: F401, F403

DEBUG = False

# Remove debug_toolbar — it interferes with staticfiles in tests
INSTALLED_APPS = [  # noqa: F405
    app for app in INSTALLED_APPS if app != "debug_toolbar"
]
MIDDLEWARE = [  # noqa: F405
    mw for mw in MIDDLEWARE if "debug_toolbar" not in mw
]

# Use plain StaticFilesStorage (no manifest required)
STORAGES = STORAGES.copy()  # noqa: F405
STORAGES["staticfiles"] = {
    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
}
