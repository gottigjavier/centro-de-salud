"""Account-related views (profile, setup wizard, user management)."""
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, redirect, render

from .forms import SetupAdminForm, UserCreateForm, UserEditForm
from .models import User


# ── Helpers de permisos ──────────────────────────────────────────────────


def is_admin(user):
    """Verifica que el usuario esté autenticado y sea administrador."""
    return user.is_authenticated and user.role == "admin"


# ── Profile ──────────────────────────────────────────────────────────────


@login_required
def profile(request):
    """Perfil del usuario logueado."""
    return render(request, "accounts/profile.html", {"user": request.user})


# ── Setup Wizard ─────────────────────────────────────────────────────────


def setup(request):
    """
    Wizard de configuración inicial.

    Crea el primer administrador del sistema. Si ya existe un admin,
    redirige al login.
    """
    # Si ya existe un admin, redirigir al login
    if User.objects.filter(role="admin", is_active=True).exists():
        return redirect("account_login")

    if request.method == "POST":
        form = SetupAdminForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Autenticar al usuario automáticamente
            login(
                request,
                user,
                backend="django.contrib.auth.backends.ModelBackend",
            )
            messages.success(
                request,
                "¡Administrador creado correctamente! Ya podés gestionar el sistema.",
            )
            return redirect("appointments:calendar")
    else:
        form = SetupAdminForm()

    return render(request, "accounts/setup.html", {"form": form})


# ── User CRUD ────────────────────────────────────────────────────────────


@login_required
@user_passes_test(is_admin)
def user_list(request):
    """Listado de usuarios del sistema (solo admin)."""
    users = User.objects.all().order_by("-date_joined")
    return render(request, "accounts/user_list.html", {"users": users})


@login_required
@user_passes_test(is_admin)
def user_create(request):
    """Crear un nuevo usuario (admin o secretario)."""
    if request.method == "POST":
        form = UserCreateForm(request.POST, request=request)
        if form.is_valid():
            user = form.save()
            messages.success(
                request,
                f"Usuario {user.email} creado correctamente.",
            )
            return redirect("accounts:user_list")
    else:
        form = UserCreateForm(request=request)

    return render(request, "accounts/user_form.html", {
        "form": form,
        "is_edit": False,
    })


@login_required
@user_passes_test(is_admin)
def user_edit(request, pk):
    """Editar un usuario existente."""
    user = get_object_or_404(User, pk=pk)

    # No permitir que un admin no-superuser edite a otro admin
    if not request.user.is_superuser and user.role == "admin" and user != request.user:
        messages.error(
            request, "No tenés permisos para editar otros administradores."
        )
        return redirect("accounts:user_list")

    if request.method == "POST":
        form = UserEditForm(request.POST, instance=user, request=request)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f"Usuario {user.email} actualizado correctamente.",
            )
            return redirect("accounts:user_list")
    else:
        form = UserEditForm(instance=user, request=request)

    return render(request, "accounts/user_form.html", {
        "form": form,
        "is_edit": True,
        "edit_user": user,
    })


@login_required
@user_passes_test(is_admin)
def user_toggle_active(request, pk):
    """Activar/desactivar un usuario."""
    user = get_object_or_404(User, pk=pk)

    # No permitir desactivarse a sí mismo
    if user == request.user:
        messages.error(request, "No podés desactivar tu propio usuario.")
        return redirect("accounts:user_list")

    # No permitir que un admin no-superuser desactive a otro admin
    if not request.user.is_superuser and user.role == "admin":
        messages.error(
            request, "No tenés permisos para modificar otros administradores."
        )
        return redirect("accounts:user_list")

    user.is_active = not user.is_active
    user.save()

    action = "activado" if user.is_active else "desactivado"
    messages.success(request, f"Usuario {user.email} {action} correctamente.")
    return redirect("accounts:user_list")
