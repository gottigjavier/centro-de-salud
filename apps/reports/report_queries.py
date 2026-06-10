"""Aggregation queries for the reports module.

All query functions accept a user (for role scoping) and a date range.
Dates can be strings in ISO format or date objects.
"""
from datetime import date, datetime, timedelta

from django.db.models import Count, Max, Q
from django.db.models.functions import ExtractHour, TruncDay, TruncMonth

from apps.accounts.models import Role
from apps.appointments.models import Appointment, AppointmentStatus
from apps.professionals.models import Professional


# ── Helpers ─────────────────────────────────────────────────────────────


def _parse_date(value):
    """Convert ISO string to date object if needed. Returns None on invalid input."""
    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return None
    return value


def _get_base_qs(user, date_from, date_to):
    """Build a scoped Appointment queryset based on user role and date range.

    Returns:
        tuple: (QuerySet, warning_flag)
            - warning_flag is True when a professional user has no associated
              Professional profile (data access is blocked).
    """
    qs = Appointment.objects.all()
    if date_from is not None:
        qs = qs.filter(date__gte=date_from)
    if date_to is not None:
        qs = qs.filter(date__lte=date_to)
    warning = False

    if user.role == Role.PROFESSIONAL:
        try:
            prof = Professional.objects.get(user=user)
            qs = qs.filter(professional=prof)
        except Professional.DoesNotExist:
            qs = Appointment.objects.none()
            warning = True

    return qs, warning


# ── Report queries ──────────────────────────────────────────────────────


def get_profesionales_report(user, date_from, date_to):
    """Appointment counts grouped by professional, broken down by status.

    Returns:
        dict with keys: rows (QuerySet), professional_only (bool), warning (bool)
    """
    qs, warning = _get_base_qs(user, date_from, date_to)

    if warning:
        return {"rows": [], "professional_only": True, "warning": True}

    rows = (
        qs.values("professional__id", "professional__first_name", "professional__last_name")
        .annotate(
            total=Count("id"),
            scheduled=Count("id", filter=Q(status=AppointmentStatus.SCHEDULED)),
            confirmed=Count("id", filter=Q(status=AppointmentStatus.CONFIRMED)),
            arrived=Count("id", filter=Q(status=AppointmentStatus.ARRIVED)),
            in_progress=Count("id", filter=Q(status=AppointmentStatus.IN_PROGRESS)),
            completed=Count("id", filter=Q(status=AppointmentStatus.COMPLETED)),
            cancelled=Count("id", filter=Q(status=AppointmentStatus.CANCELLED)),
        )
        .order_by("-total")
    )

    return {
        "rows": rows,
        "professional_only": user.role == Role.PROFESSIONAL,
        "warning": False,
    }


def get_cancelaciones_report(user, date_from, date_to):
    """Cancellation statistics: total, cancelled count, rate, and reasons breakdown.

    Returns:
        dict with keys: total, cancelled, rate, reasons (QuerySet),
                        professional_only, warning
    """
    qs, warning = _get_base_qs(user, date_from, date_to)

    if warning:
        return {
            "total": 0,
            "cancelled": 0,
            "rate": 0.0,
            "reasons": [],
            "professional_only": True,
            "warning": True,
        }

    total = qs.count()
    cancelled = qs.filter(status=AppointmentStatus.CANCELLED).count()
    rate = round((cancelled / total * 100) if total > 0 else 0.0, 1)

    reasons = (
        qs.filter(status=AppointmentStatus.CANCELLED)
        .values("cancellation_reason")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    return {
        "total": total,
        "cancelled": cancelled,
        "rate": rate,
        "reasons": reasons,
        "professional_only": user.role == Role.PROFESSIONAL,
        "warning": False,
    }


def get_recursos_report(user, date_from, date_to):
    """Resource occupancy — total appointments per resource (excluding cancelled/no_show).

    Returns:
        dict with keys: rows (QuerySet), professional_only, warning
    """
    qs, warning = _get_base_qs(user, date_from, date_to)

    if warning:
        return {"rows": [], "professional_only": True, "warning": True}

    # Exclude cancelled and no-show from occupancy counts
    qs = qs.exclude(status__in=[AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW])

    rows = (
        qs.values("resource__id", "resource__name")
        .annotate(
            total=Count("id"),
            unique_patients=Count("patient_dni", distinct=True),
        )
        .order_by("-total")
    )

    return {"rows": rows, "professional_only": user.role == Role.PROFESSIONAL, "warning": False}


def get_tendencia_report(user, date_from, date_to):
    """Appointment trend over time — daily (≤60 day range) or monthly aggregation.

    Returns:
        dict with keys: labels (list[str]), data (list[int]), is_daily (bool),
                        professional_only, warning
    """
    qs, warning = _get_base_qs(user, date_from, date_to)

    if warning:
        return {
            "labels": [],
            "data": [],
            "is_daily": False,
            "professional_only": True,
            "warning": True,
        }

    # Determine granularity from date range span
    df = _parse_date(date_from) if isinstance(date_from, str) else date_from
    dt = _parse_date(date_to) if isinstance(date_to, str) else date_to
    if df and dt:
        delta = (dt - df).days
    else:
        delta = 30

    is_daily = delta <= 60
    trunc = TruncDay if is_daily else TruncMonth
    format_str = "%d/%m" if is_daily else "%m/%Y"

    trend = (
        qs.annotate(period=trunc("date"))
        .values("period")
        .annotate(count=Count("id"))
        .order_by("period")
    )

    raw_data = {t["period"]: t["count"] for t in trend if t["period"]}

    if df and dt:
        if is_daily:
            current = df
            filled_labels = []
            filled_data = []
            while current <= dt:
                filled_labels.append(current.strftime(format_str))
                filled_data.append(raw_data.get(current, 0))
                current += timedelta(days=1)
        else:
            current = date(df.year, df.month, 1)
            filled_labels = []
            filled_data = []
            while current <= dt:
                filled_labels.append(current.strftime(format_str))
                filled_data.append(raw_data.get(current, 0))
                if current.month == 12:
                    current = date(current.year + 1, 1, 1)
                else:
                    current = date(current.year, current.month + 1, 1)
        labels, data = filled_labels, filled_data
    else:
        labels = [t["period"].strftime(format_str) if t["period"] else "" for t in trend]
        data = [t["count"] for t in trend]

    return {
        "labels": labels,
        "data": data,
        "is_daily": is_daily,
        "professional_only": user.role == Role.PROFESSIONAL,
        "warning": False,
    }


def get_frecuentes_report(user, date_from, date_to, limit=20):
    """Top N most frequent patients by appointment count in the date range.

    Returns:
        dict with keys: rows (QuerySet), professional_only, warning
    """
    qs, warning = _get_base_qs(user, date_from, date_to)

    if warning:
        return {"rows": [], "professional_only": True, "warning": True}

    rows = (
        qs.values("patient_name", "patient_dni")
        .annotate(
            count=Count("id"),
            last_date=Max("date"),
        )
        .order_by("-count")[:limit]
    )

    return {"rows": rows, "professional_only": user.role == Role.PROFESSIONAL, "warning": False}


def get_horas_pico_report(user, date_from, date_to):
    """Appointment distribution by hour of the day (excluding cancelled/no_show).

    Returns:
        dict with keys: rows (list[dict]) — each with "label" (str) and "total" (int),
                        professional_only, warning
    """
    qs, warning = _get_base_qs(user, date_from, date_to)

    if warning:
        return {"rows": [], "professional_only": True, "warning": True}

    # Exclude cancelled and no-show
    qs = qs.exclude(status__in=[AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW])

    hours = (
        qs.annotate(hour=ExtractHour("start_time"))
        .values("hour")
        .annotate(total=Count("id"))
        .order_by("-total")
    )

    rows = []
    for h in hours:
        if h["hour"] is not None:
            hour_int = int(h["hour"])
            label = f"{hour_int:02d}:00 - {hour_int + 1:02d}:00"
            rows.append({"label": label, "total": h["total"]})

    return {"rows": rows, "professional_only": user.role == Role.PROFESSIONAL, "warning": False}
