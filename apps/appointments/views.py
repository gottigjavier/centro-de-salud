"""Views for appointment management — CRUD, HTMX, transitions."""
from collections import OrderedDict
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.professionals.models import Professional, ProfessionalResourceAssignment
from apps.resources.models import Resource

from .forms import AppointmentForm, CancelAppointmentForm
from .models import APPOINTMENT_VALID_TRANSITIONS, Appointment, AppointmentStatus


# ── Permission helpers ──────────────────────────────────────────────────


def require_role(*roles):
    """Decorator: require login + one of the given roles, else 403 Forbidden."""
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


# ── Calendar (placeholder existente) ────────────────────────────────────


@login_required
def calendar_view_placeholder(request):
    """Placeholder para la vista calendario (fuera de scope para Phase A)."""
    return render(request, "appointments/calendar.html")


# ── Appointment List ────────────────────────────────────────────────────


@login_required
def appointment_list(request):
    """Listado paginado de turnos con filtros, paginación y scoping por rol."""
    qs = Appointment.objects.select_related("resource", "professional").order_by("date", "start_time")

    # Scoping por rol profesional
    professional_warning = None
    if request.user.role == "professional":
        try:
            professional = Professional.objects.get(user=request.user)
            qs = qs.filter(professional=professional)
        except Professional.DoesNotExist:
            qs = Appointment.objects.none()
            professional_warning = "No tenés un perfil de profesional asociado a tu usuario. Contactá al administrador."

    # Filtros desde query params
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")
    status_filter = request.GET.get("status", "")
    resource_filter = request.GET.get("resource", "")

    if date_from:
        try:
            qs = qs.filter(date__gte=datetime.strptime(date_from, "%Y-%m-%d").date())
        except ValueError:
            pass
    if date_to:
        try:
            qs = qs.filter(date__lte=datetime.strptime(date_to, "%Y-%m-%d").date())
        except ValueError:
            pass
    if status_filter:
        qs = qs.filter(status=status_filter)
    if resource_filter and resource_filter.isdigit():
        qs = qs.filter(resource_id=int(resource_filter))

    # Default filter: today
    if not date_from and not date_to:
        today = timezone.localdate()
        qs = qs.filter(date=today)

    # Paginación
    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "appointments": page_obj,
        "is_admin": es_admin(request.user),
        "status_choices": AppointmentStatus.choices,
        "resources": Resource.objects.filter(is_active=True),
        "professional_warning": professional_warning,
        "current_filters": {
            "date_from": date_from,
            "date_to": date_to,
            "status": status_filter,
            "resource": resource_filter,
        },
    }
    return render(request, "appointments/appointment_list.html", context)


# ── Appointment Detail ──────────────────────────────────────────────────


@login_required
def appointment_detail(request, pk):
    """Detalle de turno con botones de transición de estado y scoping por rol."""
    appointment = get_object_or_404(
        Appointment.objects.select_related("resource", "professional", "created_by"),
        pk=pk,
    )

    # Scoping por rol profesional
    if request.user.role == "professional":
        try:
            professional = Professional.objects.get(user=request.user)
            if appointment.professional != professional:
                raise PermissionDenied
        except Professional.DoesNotExist:
            raise PermissionDenied

    # Transiciones válidas para el estado actual
    valid_transitions = APPOINTMENT_VALID_TRANSITIONS.get(appointment.status, [])

    context = {
        "appointment": appointment,
        "valid_transitions": valid_transitions,
        "is_admin": es_admin(request.user),
        "is_secretary": request.user.role == "secretary",
        "is_professional": request.user.role == "professional",
    }
    return render(request, "appointments/appointment_detail.html", context)


# ── Appointment Create ──────────────────────────────────────────────────


@require_role("admin", "secretary")
def appointment_create(request):
    """Crear nuevo turno con selects dinámicos HTMX."""
    if request.method == "POST":
        form = AppointmentForm(request.POST)
        if form.is_valid():
            appointment = form.save(commit=False)
            appointment.created_by = request.user
            try:
                appointment.full_clean()  # Doble validación (modelo + form)
                appointment.save()
                messages.success(request, f"Turno creado para {appointment.patient_name}.")
                return redirect("appointments:detail", pk=appointment.pk)
            except ValidationError as e:
                for field, errors in e.message_dict.items():
                    for error in errors:
                        if field in form.fields:
                            form.add_error(field, error)
                        else:
                            form.add_error(None, error)
        # Fall through to re-render on error
    else:
        form = AppointmentForm()

    return render(request, "appointments/appointment_form.html", {
        "form": form,
        "is_edit": False,
        "resources": Resource.objects.filter(is_active=True),
    })


# ── Appointment Update ──────────────────────────────────────────────────


@require_role("admin", "secretary")
def appointment_update(request, pk):
    """Editar datos del paciente de un turno existente (edición parcial)."""
    appointment = get_object_or_404(Appointment, pk=pk)

    if request.method == "POST":
        form = AppointmentForm(request.POST, instance=appointment, for_update=True)
        if form.is_valid():
            form.save()
            messages.success(request, "Turno actualizado exitosamente.")
            return redirect("appointments:detail", pk=appointment.pk)
    else:
        form = AppointmentForm(instance=appointment, for_update=True)

    return render(request, "appointments/appointment_form.html", {
        "form": form,
        "is_edit": True,
        "edit_appointment": appointment,
    })


# ── Appointment Cancel ──────────────────────────────────────────────────


@require_role("admin", "secretary", "professional")
def appointment_cancel(request, pk):
    """Cancelar turno con motivo obligatorio. Accesible por admin, secretary y professional (propios)."""
    appointment = get_object_or_404(Appointment, pk=pk)

    # Scoping por rol profesional
    if request.user.role == "professional":
        try:
            professional = Professional.objects.get(user=request.user)
            if appointment.professional != professional:
                raise PermissionDenied
        except Professional.DoesNotExist:
            raise PermissionDenied

    if request.method == "POST":
        form = CancelAppointmentForm(request.POST)
        if form.is_valid():
            appointment.status = AppointmentStatus.CANCELLED
            appointment.cancellation_reason = form.cleaned_data["reason"]
            try:
                appointment.full_clean()  # Valida state machine
                appointment.save(update_fields=["status", "cancellation_reason"])
                messages.success(request, "Turno cancelado exitosamente.")
                return redirect("appointments:detail", pk=appointment.pk)
            except ValidationError as e:
                for field, errors in e.message_dict.items():
                    for error in errors:
                        if field in form.fields:
                            form.add_error(field, error)
                        else:
                            form.add_error(None, error)
    else:
        form = CancelAppointmentForm()

    return render(request, "appointments/appointment_cancel.html", {
        "form": form,
        "appointment": appointment,
    })


# ── Appointment Transition ──────────────────────────────────────────────


@require_role("admin", "secretary", "professional")
def appointment_transition(request, pk, status):
    """Cambiar estado de un turno vía POST. Valida transición en model.clean()."""
    if request.method != "POST":
        return redirect("appointments:detail", pk=pk)

    appointment = get_object_or_404(
        Appointment.objects.select_related("professional"),
        pk=pk,
    )

    # Validar que el nuevo estado sea una opción válida de AppointmentStatus
    valid_status_values = [s.value for s in AppointmentStatus]
    if status not in valid_status_values:
        return HttpResponseBadRequest("Estado inválido")

    # Scoping por rol profesional
    if request.user.role == "professional":
        try:
            professional = Professional.objects.get(user=request.user)
            if appointment.professional != professional:
                raise PermissionDenied
            # Professional solo puede: CONFIRMED, IN_PROGRESS, COMPLETED
            allowed = [AppointmentStatus.CONFIRMED.value, AppointmentStatus.IN_PROGRESS.value, AppointmentStatus.COMPLETED.value]
            if status not in allowed:
                raise PermissionDenied
        except Professional.DoesNotExist:
            raise PermissionDenied

    # Aplicar transición
    old_status = appointment.status
    appointment.status = status

    try:
        appointment.full_clean()  # Valida state machine (V-001..V-008)
        appointment.save(update_fields=["status"])
    except ValidationError as e:
        return HttpResponseBadRequest(str(e))

    # HTMX response: return updated row with HX-Trigger header
    if request.htmx:
        transitions = APPOINTMENT_VALID_TRANSITIONS.get(appointment.status, [])
        if request.user.role == "professional":
            prof_allowed = [
                AppointmentStatus.CONFIRMED.value,
                AppointmentStatus.IN_PROGRESS.value,
                AppointmentStatus.COMPLETED.value,
            ]
            transitions = [t for t in transitions if t.value in prof_allowed]
        appointment.valid_transitions = [t.value for t in transitions]

        context = {"appointment": appointment}
        response = render(request, "appointments/partials/_agenda_row.html", context)
        response["HX-Trigger"] = "agenda-updated"
        return response

    messages.success(
        request,
        f"Turno {old_status} → {status} actualizado correctamente.",
    )
    return redirect("appointments:detail", pk=pk)


# ── Agenda del Día ─────────────────────────────────────────────────────


def _get_agenda_data(request):
    """Shared helper for agenda view and HTMX partials.
    Returns (grouped, stats, professionals, warning)"""
    today = timezone.localdate()
    professional_filter = request.GET.get("professional", "")

    qs = Appointment.objects.filter(date=today).select_related(
        "resource", "professional"
    ).order_by("professional__last_name", "professional__first_name", "start_time")

    # Role scoping
    warning = None
    if request.user.role == "professional":
        try:
            prof = Professional.objects.get(user=request.user)
            qs = qs.filter(professional=prof)
        except Professional.DoesNotExist:
            qs = Appointment.objects.none()
            warning = "No tenés un perfil de profesional asociado a tu usuario."

    # Filter by professional
    if professional_filter and professional_filter.isdigit():
        qs = qs.filter(professional_id=int(professional_filter))

    # Stats
    stats = {"total": qs.count()}
    for choice in AppointmentStatus:
        stats[choice.value] = qs.filter(status=choice).count()

    # Group by professional with valid transitions
    grouped = OrderedDict()
    for appt in qs:
        # Compute valid transitions as string values for template
        transitions = [t.value for t in APPOINTMENT_VALID_TRANSITIONS.get(appt.status, [])]

        # Filter by role
        if request.user.role == "professional":
            prof_allowed = [
                AppointmentStatus.CONFIRMED.value,
                AppointmentStatus.IN_PROGRESS.value,
                AppointmentStatus.COMPLETED.value,
            ]
            transitions = [t for t in transitions if t in prof_allowed]

        appt.valid_transitions = transitions

        key = appt.professional_id
        if key not in grouped:
            grouped[key] = {
                "professional": appt.professional,
                "appointments": [],
            }
        grouped[key]["appointments"].append(appt)

    # Professionals with today's appointments (for filter dropdown)
    profs_with_appts = Professional.objects.filter(
        appointments__date=today, is_active=True
    ).distinct().order_by("last_name", "first_name")

    return grouped, stats, profs_with_appts, warning


@login_required
def agenda_view(request):
    """Pantalla principal de agenda del día con turnos agrupados por profesional + stats."""
    grouped, stats, profs_with_appts, warning = _get_agenda_data(request)
    today = timezone.localdate()

    context = {
        "grouped": grouped,
        "stats": stats,
        "today": today,
        "is_admin": es_admin(request.user),
        "is_secretary": request.user.role == "secretary",
        "is_professional": request.user.role == "professional",
        "professionals": profs_with_appts,
        "selected_professional": request.GET.get("professional", ""),
        "professional_warning": warning,
    }
    return render(request, "appointments/agenda.html", context)


@login_required
def htmx_agenda_stats(request):
    """HTMX partial: stats cards actualizadas."""
    _, stats, _, _ = _get_agenda_data(request)
    return render(request, "appointments/partials/_agenda_stats.html", {
        "stats": stats,
    })


@login_required
def htmx_agenda_table(request):
    """HTMX partial: tabla agrupada por profesional."""
    grouped, _, _, _ = _get_agenda_data(request)
    return render(request, "appointments/partials/_agenda_table.html", {
        "grouped": grouped,
    })


# ── Slot calculation ────────────────────────────────────────────────────


def get_available_slots(resource_id, professional_id, date):
    """Return list of (start_time, end_time) available slots for a given day."""
    SLOT_DURATION = timedelta(minutes=30)
    day_of_week = date.weekday()

    assignments = ProfessionalResourceAssignment.objects.filter(
        professional_id=professional_id,
        resource_id=resource_id,
        is_active=True,
    ).filter(
        Q(day_of_week=day_of_week) | Q(day_of_week__isnull=True),
    ).filter(
        Q(start_date__lte=date) | Q(start_date__isnull=True),
    ).filter(
        Q(end_date__gte=date) | Q(end_date__isnull=True),
    )

    if not assignments.exists():
        return []

    # Turnos ocupados (no cancelados)
    booked = Appointment.objects.filter(
        professional_id=professional_id,
        resource_id=resource_id,
        date=date,
    ).exclude(
        status__in=[AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW],
    ).values_list("start_time", "end_time")

    booked_slots = [(b[0], b[1]) for b in booked]

    def overlaps(s, e):
        for bs, be in booked_slots:
            if s < be and e > bs:
                return True
        return False

    slots = []
    for assignment in assignments:
        current = datetime.combine(date, assignment.start_time)
        end_dt = datetime.combine(date, assignment.end_time)
        while current + SLOT_DURATION <= end_dt:
            slot_start = current.time()
            slot_end = (current + SLOT_DURATION).time()
            if not overlaps(slot_start, slot_end):
                slots.append((slot_start, slot_end))
            current += SLOT_DURATION

    return slots


# ── HTMX: Profesionales por recurso+fecha ────────────────────────────────


@login_required
def htmx_profesionales(request, resource_id):
    """HTMX: Devuelve <select> con profesionales disponibles para recurso+fecha."""
    date_str = request.GET.get("date", "")
    if not date_str:
        return HttpResponse(
            '<select name="professional" id="id_professional" class="form-input">'
            '<option value="">Seleccioná una fecha primero</option></select>'
        )

    try:
        date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return HttpResponse(
            '<select name="professional" id="id_professional" class="form-input">'
            '<option value="">Fecha inválida</option></select>'
        )

    day_of_week = date.weekday()

    # Professional IDs from active assignments
    assignment_ids = ProfessionalResourceAssignment.objects.filter(
        resource_id=resource_id,
        is_active=True,
    ).filter(
        Q(day_of_week=day_of_week) | Q(day_of_week__isnull=True),
    ).filter(
        Q(start_date__lte=date) | Q(start_date__isnull=True),
    ).filter(
        Q(end_date__gte=date) | Q(end_date__isnull=True),
    ).values_list("professional_id", flat=True).distinct()

    professionals = Professional.objects.filter(
        pk__in=set(assignment_ids), is_active=True
    ).order_by("last_name", "first_name")

    return render(request, "appointments/partials/_profesionales_select.html", {
        "professionals": professionals,
        "date": date_str,
        "resource_id": resource_id,
    })


# ── HTMX: Horarios por profesional+recurso+fecha ────────────────────────


@login_required
def htmx_horarios(request, professional_id):
    """HTMX: Devuelve <select> con slots disponibles para profesional+recurso+fecha."""
    date_str = request.GET.get("date", "")
    resource_id = request.GET.get("resource_id", "")

    if not date_str or not resource_id:
        return HttpResponse(
            '<select name="slot" id="id_slots" class="form-input">'
            '<option value="">Faltan parámetros</option></select>'
        )

    try:
        date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return HttpResponse(
            '<select name="slot" id="id_slots" class="form-input">'
            '<option value="">Fecha inválida</option></select>'
        )

    slots = get_available_slots(resource_id, professional_id, date)

    return render(request, "appointments/partials/_horarios_select.html", {
        "slots": slots,
        "date": date_str,
    })
