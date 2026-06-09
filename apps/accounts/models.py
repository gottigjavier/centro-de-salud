"""Custom User model with role-based access control."""
from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.TextChoices):
    ADMIN = "admin", "Administrador"
    SECRETARY = "secretary", "Secretario"
    PROFESSIONAL = "professional", "Profesional"


class User(AbstractUser):
    """
    Custom user with email as the unique identifier.

    Roles control access to views and data scoping.
    """

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.SECRETARY,
        verbose_name="rol",
    )
    phone = models.CharField(
        max_length=20, blank=True, verbose_name="teléfono"
    )

    # Disable username — use email for auth
    username = None  # type: ignore[assignment]
    email = models.EmailField(
        unique=True, verbose_name="correo electrónico"
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"

    def __str__(self):
        return f"{self.get_full_name() or self.email} ({self.get_role_display()})"
