"""Base models and abstract mixins shared across all apps."""
from django.db import models


class TimeStampedMixin(models.Model):
    """Adds created_at and updated_at timestamp fields."""

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="creado")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="actualizado")

    class Meta:
        abstract = True


class ActiveMixin(models.Model):
    """Adds an is_active flag for soft-disable."""

    is_active = models.BooleanField(default=True, verbose_name="activo")

    class Meta:
        abstract = True
