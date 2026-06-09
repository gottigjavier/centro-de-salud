"""Views for resource management."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import NonWorkingDayForm, ResourceForm, ResourceScheduleForm
from .models import NonWorkingDay, Resource, ResourceSchedule


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


# ── Resource CRUD ──────────────────────────────────────────────────────


@login_required
def resource_list(request):
    """Listado paginado de recursos. Accesible por cualquier rol autenticado."""
    recursos = Resource.objects.all().order_by("name")
    paginator = Paginator(recursos, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    return render(request, "resources/resource_list.html", {
        "resources": page_obj,
        "is_admin": es_admin(request.user),
    })


@login_required
def resource_detail(request, pk):
    """Detalle de un recurso con sus horarios activos."""
    resource = get_object_or_404(Resource, pk=pk)
    schedules = ResourceSchedule.objects.filter(
        resource=resource, is_active=True
    ).order_by("day_of_week", "start_time")
    schedule_form = ResourceScheduleForm(resource=resource) if es_admin(request.user) else None
    return render(request, "resources/resource_detail.html", {
        "resource": resource,
        "schedules": schedules,
        "schedule_form": schedule_form,
        "is_admin": es_admin(request.user),
    })


@require_role("admin")
def resource_create(request):
    """Crear un nuevo recurso (solo admin)."""
    if request.method == "POST":
        form = ResourceForm(request.POST)
        if form.is_valid():
            resource = form.save()
            messages.success(request, "Recurso creado exitosamente.")
            return redirect("resources:detail", pk=resource.pk)
    else:
        form = ResourceForm()

    return render(request, "resources/resource_form.html", {
        "form": form,
        "is_edit": False,
        "is_admin": True,
    })


@require_role("admin")
def resource_update(request, pk):
    """Editar un recurso existente (solo admin)."""
    resource = get_object_or_404(Resource, pk=pk)
    if request.method == "POST":
        form = ResourceForm(request.POST, instance=resource)
        if form.is_valid():
            form.save()
            messages.success(request, "Recurso actualizado exitosamente.")
            return redirect("resources:detail", pk=resource.pk)
    else:
        form = ResourceForm(instance=resource)

    return render(request, "resources/resource_form.html", {
        "form": form,
        "is_edit": True,
        "edit_resource": resource,
        "is_admin": True,
    })


@require_role("admin")
def resource_toggle_active(request, pk):
    """Activar/desactivar un recurso (soft delete). Solo POST."""
    resource = get_object_or_404(Resource, pk=pk)

    if request.method == "POST":
        resource.is_active = not resource.is_active
        resource.save()
        action = "activado" if resource.is_active else "desactivado"
        messages.success(request, f"Recurso {action} exitosamente.")

        # Soporte HTMX: devolver partial del row actualizado
        if request.headers.get("HX-Request") == "true":
            return render(request, "resources/partials/_resource_row.html", {
                "resource": resource,
            })

        return redirect("resources:list")

    # GET: redirigir al listado (el toggle requiere POST)
    return redirect("resources:list")


# ── ResourceSchedule HTMX ──────────────────────────────────────────────


@require_role("admin")
def schedule_add(request, pk):
    """Agregar horario a un recurso vía HTMX inline (solo admin)."""
    resource = get_object_or_404(Resource, pk=pk)

    if request.method == "POST":
        form = ResourceScheduleForm(request.POST, resource=resource)
        if form.is_valid():
            schedule = form.save(commit=False)
            schedule.resource = resource
            schedule.save()
            messages.success(request, "Horario agregado exitosamente.")
        else:
            # HTMX: devolver form con errores inline
            return render(
                request,
                "resources/partials/_schedule_form.html",
                {"form": form, "resource": resource, "is_admin": True},
                status=422,
            )

        # Devolver lista de horarios actualizada
        schedules = ResourceSchedule.objects.filter(
            resource=resource, is_active=True
        ).order_by("day_of_week", "start_time")
        return render(request, "resources/partials/_schedule_list.html", {
            "schedules": schedules,
            "resource": resource,
            "is_admin": True,
        })

    return redirect("resources:detail", pk=pk)


@require_role("admin")
def schedule_delete(request, pk):
    """Eliminar (soft delete) un horario de recurso vía HTMX (solo admin)."""
    schedule = get_object_or_404(ResourceSchedule, pk=pk)
    resource = schedule.resource

    if request.method == "POST":
        schedule.is_active = False
        schedule.save()
        messages.success(request, "Horario eliminado exitosamente.")

        schedules = ResourceSchedule.objects.filter(
            resource=resource, is_active=True
        ).order_by("day_of_week", "start_time")

        if request.headers.get("HX-Request") == "true":
            return render(request, "resources/partials/_schedule_list.html", {
                "schedules": schedules,
                "resource": resource,
                "is_admin": True,
            })

        return redirect("resources:detail", pk=resource.pk)

    return redirect("resources:detail", pk=resource.pk)


# ── NonWorkingDay CRUD ────────────────────────────────────────────────


@require_role("admin", "secretary")
def nonworkingday_list(request):
    """Listado paginado de días no laborables. Accesible por admin y secretaría."""
    days = NonWorkingDay.objects.all().order_by("-date")
    paginator = Paginator(days, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    return render(request, "resources/nonworkingday_list.html", {
        "nonworkingdays": page_obj,
        "is_admin": es_admin(request.user),
    })


@require_role("admin")
def nonworkingday_create(request):
    """Crear un día no laborable (solo admin)."""
    if request.method == "POST":
        form = NonWorkingDayForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Día no laborable creado exitosamente.")
            return redirect("resources:nonworkingday_list")
        messages.error(request, "Corregí los errores en el formulario.")
    else:
        form = NonWorkingDayForm()

    return render(request, "resources/nonworkingday_form.html", {
        "form": form,
        "is_admin": True,
    })


@require_role("admin")
def nonworkingday_delete(request, pk):
    """Eliminar un día no laborable (hard delete, solo admin). POST only."""
    nwd = get_object_or_404(NonWorkingDay, pk=pk)

    if request.method == "POST":
        nwd.delete()
        messages.success(request, "Día no laborable eliminado exitosamente.")

        # Soporte HTMX: respuesta vacía con trigger para refrescar lista
        if request.headers.get("HX-Request") == "true":
            response = HttpResponse()
            response["HX-Trigger"] = "nonworkingday-updated"
            return response

        return redirect("resources:nonworkingday_list")

    # GET: redirigir al listado con advertencia
    messages.warning(request, "Usá el botón 'Eliminar' para confirmar.")
    return redirect("resources:nonworkingday_list")
