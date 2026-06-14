"""Views for professional management."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ProfessionalForm, ProfessionalResourceAssignmentForm
from .models import Professional, ProfessionalResourceAssignment


# ── Permission helpers ──────────────────────────────────────────────────


def require_role(*roles):
    """Decorator: require login + one of the given roles, else 403 Forbidden.

    Acts as a replacement for ``@login_required + @user_passes_test``
    but returns **403** for authenticated users who fail the role
    check (``user_passes_test`` redirects to login instead).
    """

    def decorator(view_func):
        @login_required
        def wrapper(request, *args, **kwargs):
            if request.user.role not in roles:
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def es_admin(user):
    """Check if user is authenticated with admin role (utility)."""
    return user.is_authenticated and user.role == "admin"


# ── Professional CRUD ──────────────────────────────────────────────────


@login_required
def professional_list(request):
    """Listado paginado de profesionales. Accesible por cualquier rol autenticado."""
    profesionales = Professional.objects.all().order_by("last_name", "first_name")
    paginator = Paginator(profesionales, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    return render(request, "professionals/professional_list.html", {
        "professionals": page_obj,
        "is_admin": es_admin(request.user),
    })


@login_required
def professional_detail(request, pk):
    """Detalle de un profesional con sus asignaciones activas."""
    professional = get_object_or_404(Professional, pk=pk)
    assignments = ProfessionalResourceAssignment.objects.filter(
        professional=professional, is_active=True
    ).order_by("day_of_week", "start_time")
    form = (
        ProfessionalResourceAssignmentForm(professional=professional)
        if es_admin(request.user)
        else None
    )
    return render(request, "professionals/professional_detail.html", {
        "professional": professional,
        "assignments": assignments,
        "form": form,
        "is_admin": es_admin(request.user),
    })


@require_role("admin")
def professional_create(request):
    """Crear un nuevo profesional (solo admin)."""
    if request.method == "POST":
        form = ProfessionalForm(request.POST)
        if form.is_valid():
            professional = form.save()
            messages.success(request, "Profesional creado exitosamente.")
            return redirect("professionals:detail", pk=professional.pk)
    else:
        form = ProfessionalForm()

    return render(request, "professionals/professional_form.html", {
        "form": form,
        "is_edit": False,
    })


@require_role("admin")
def professional_update(request, pk):
    """Editar un profesional existente (solo admin)."""
    professional = get_object_or_404(Professional, pk=pk)
    if request.method == "POST":
        form = ProfessionalForm(request.POST, instance=professional)
        if form.is_valid():
            form.save()
            messages.success(request, "Profesional actualizado exitosamente.")
            return redirect("professionals:detail", pk=professional.pk)
    else:
        form = ProfessionalForm(instance=professional)

    return render(request, "professionals/professional_form.html", {
        "form": form,
        "is_edit": True,
        "edit_professional": professional,
    })


@require_role("admin")
def professional_toggle_active(request, pk):
    """Activar/desactivar un profesional (soft delete). GET muestra confirmación, POST ejecuta."""
    professional = get_object_or_404(Professional, pk=pk)

    if request.method == "POST":
        professional.is_active = not professional.is_active
        professional.save(update_fields=["is_active"])
        action = "activado" if professional.is_active else "desactivado"
        messages.success(request, f"Profesional {action} exitosamente.")
        return redirect("professionals:list")

    # GET: mostrar página de confirmación
    return render(request, "professionals/professional_confirm_delete.html", {
        "professional": professional,
    })


# ── ProfessionalResourceAssignment HTMX ────────────────────────────────


@require_role("admin")
def assignment_add(request, pk):
    """Agregar asignación a un profesional vía HTMX inline (solo admin)."""
    professional = get_object_or_404(Professional, pk=pk)

    if request.method == "POST":
        form = ProfessionalResourceAssignmentForm(
            request.POST, professional=professional
        )
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.professional = professional
            assignment.save()
            messages.success(request, "Asignación agregada exitosamente.")
        else:
            # HTMX: devolver form con errores inline
            return render(
                request,
                "professionals/partials/_assignment_form.html",
                {"form": form, "professional": professional, "is_admin": True},
                status=422,
            )

        # Devolver lista de asignaciones actualizada
        assignments = ProfessionalResourceAssignment.objects.filter(
            professional=professional, is_active=True
        ).order_by("day_of_week", "start_time")
        return render(request, "professionals/partials/_assignment_list.html", {
            "assignments": assignments,
            "professional": professional,
            "is_admin": True,
        })

    return redirect("professionals:detail", pk=pk)


@require_role("admin")
def assignment_delete(request, pk):
    """Eliminar (soft delete) una asignación vía HTMX (solo admin)."""
    assignment = get_object_or_404(ProfessionalResourceAssignment, pk=pk)
    professional = assignment.professional

    if request.method == "POST":
        assignment.is_active = False
        assignment.save(update_fields=["is_active"])
        messages.success(request, "Asignación eliminada exitosamente.")

        assignments = ProfessionalResourceAssignment.objects.filter(
            professional=professional, is_active=True
        ).order_by("day_of_week", "start_time")

        return render(request, "professionals/partials/_assignment_list.html", {
            "assignments": assignments,
            "professional": professional,
            "is_admin": True,
        })

    return redirect("professionals:detail", pk=professional.pk)
