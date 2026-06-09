"""Middleware para verificar existencia de administrador."""

from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse, NoReverseMatch


class AdminSetupMiddleware:
    """
    Middleware que verifica si existe al menos un usuario administrador.

    Si no hay ningún admin registrado, redirige a la página de setup
    para crear el primer administrador del sistema.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Solo verificar si no estamos ya en la página de setup
        try:
            setup_path = reverse("accounts:setup")
        except NoReverseMatch:
            # Si la URL no está configurada aún (setup inicial), no intervenir
            return self.get_response(request)

        if not request.path.startswith(setup_path):
            from .models import User

            if not User.objects.filter(role="admin", is_active=True).exists():
                # Usuario autenticado pero no es admin → dejar pasar (no redirigir)
                if request.user.is_authenticated and request.user.role != "admin":
                    pass
                elif not request.user.is_authenticated:
                    # Usuario no autenticado y no hay admin → redirigir a setup
                    return redirect("accounts:setup")

        response = self.get_response(request)
        return response
