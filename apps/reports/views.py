"""Views for the reports module — dashboard, widget partials, and CSV exports."""
import json
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseBadRequest
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.accounts.models import Role

from .report_queries import (
    get_cancelaciones_report,
    get_frecuentes_report,
    get_horas_pico_report,
    get_profesionales_report,
    get_recursos_report,
    get_tendencia_report,
)
from .services import csv_response


# ── Local permission helpers (NOT imported from other apps) ─────────────


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


def _validate_date_or_400(date_str, field_name):
    """Parse date string and return date object, or HttpResponseBadRequest on invalid input."""
    if date_str:
        parsed = parse_date(date_str)
        if parsed is None:
            return HttpResponseBadRequest(
                f"<div class='p-4 text-red-600'>Fecha inválida: {field_name}</div>"
            )
        return parsed
    return None


def es_admin(user):
    """Check if user is authenticated with admin role."""
    return user.is_authenticated and user.role == Role.ADMIN


# ── Chart config builders ──────────────────────────────────────────────


def _chart_profesionales(rows):
    """Build bar chart config for profesionales widget."""
    labels = [f"{r['professional__last_name']}, {r['professional__first_name']}" for r in rows]
    totals = [r["total"] for r in rows]
    return {
        "type": "bar",
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "label": "Turnos",
                    "data": totals,
                    "backgroundColor": "rgba(59, 130, 246, 0.5)",
                    "borderColor": "rgb(59, 130, 246)",
                    "borderWidth": 1,
                }
            ],
        },
        "options": {
            "responsive": True,
            "maintainAspectRatio": False,
            "plugins": {"legend": {"display": False}},
            "scales": {
                "y": {"beginAtZero": True, "ticks": {"stepSize": 1}},
                "x": {"ticks": {"maxRotation": 45}},
            },
        },
    }


def _chart_cancelaciones(reasons):
    """Build pie chart config for cancelaciones widget."""
    labels = [r["cancellation_reason"] or "Sin motivo" for r in reasons]
    counts = [r["count"] for r in reasons]
    return {
        "type": "pie",
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "data": counts,
                    "backgroundColor": [
                        "rgba(239, 68, 68, 0.7)",
                        "rgba(251, 146, 60, 0.7)",
                        "rgba(234, 179, 8, 0.7)",
                        "rgba(59, 130, 246, 0.7)",
                        "rgba(16, 185, 129, 0.7)",
                    ],
                }
            ],
        },
        "options": {
            "responsive": True,
            "maintainAspectRatio": False,
            "plugins": {"legend": {"position": "bottom"}},
        },
    }


def _chart_recursos(rows):
    """Build bar chart config for recursos widget."""
    labels = [r["resource__name"] for r in rows]
    totals = [r["total"] for r in rows]
    return {
        "type": "bar",
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "label": "Turnos",
                    "data": totals,
                    "backgroundColor": "rgba(16, 185, 129, 0.5)",
                    "borderColor": "rgb(16, 185, 129)",
                    "borderWidth": 1,
                }
            ],
        },
        "options": {
            "responsive": True,
            "maintainAspectRatio": False,
            "plugins": {"legend": {"display": False}},
            "scales": {
                "y": {"beginAtZero": True, "ticks": {"stepSize": 1}},
            },
        },
    }


def _chart_tendencia(labels, data):
    """Build line chart config for tendencia widget."""
    return {
        "type": "line",
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "label": "Turnos",
                    "data": data,
                    "fill": True,
                    "borderColor": "rgb(59, 130, 246)",
                    "backgroundColor": "rgba(59, 130, 246, 0.1)",
                    "tension": 0.3,
                }
            ],
        },
        "options": {
            "responsive": True,
            "maintainAspectRatio": False,
            "plugins": {"legend": {"display": False}},
            "scales": {
                "y": {"beginAtZero": True, "ticks": {"stepSize": 1}},
            },
        },
    }


def _chart_horas_pico(rows):
    """Build bar chart config for horas pico widget."""
    labels = [r["label"] for r in rows]
    totals = [r["total"] for r in rows]
    return {
        "type": "bar",
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "label": "Turnos",
                    "data": totals,
                    "backgroundColor": "rgba(139, 92, 246, 0.5)",
                    "borderColor": "rgb(139, 92, 246)",
                    "borderWidth": 1,
                }
            ],
        },
        "options": {
            "responsive": True,
            "maintainAspectRatio": False,
            "plugins": {"legend": {"display": False}},
            "scales": {
                "y": {"beginAtZero": True, "ticks": {"stepSize": 1}},
            },
        },
    }


# ── Dashboard view ─────────────────────────────────────────────────────


@login_required
def reports_dashboard(request):
    """Main reports dashboard page — renders with all widget data and Chart.js."""
    today = timezone.localdate()
    default_from = (today - timedelta(days=30)).isoformat()
    default_to = today.isoformat()

    date_from = request.GET.get("date_from", default_from)
    date_to = request.GET.get("date_to", default_to)

    result = _validate_date_or_400(date_from, "Fecha desde")
    if isinstance(result, HttpResponseBadRequest):
        return result

    result = _validate_date_or_400(date_to, "Fecha hasta")
    if isinstance(result, HttpResponseBadRequest):
        return result

    context = {
        "date_from": date_from,
        "date_to": date_to,
        "is_admin": es_admin(request.user),
        "is_secretary": request.user.role == Role.SECRETARY,
        "is_professional": request.user.role == Role.PROFESSIONAL,
    }
    return render(request, "reports/dashboard.html", context)


# ── Widget views (HTMX partial endpoints) ──────────────────────────────


def _prepare_profesionales_data(user, date_from, date_to):
    """Fetch and prepare profesionales widget data with chart config."""
    data = get_profesionales_report(user, date_from, date_to)
    data["date_from"] = date_from
    data["date_to"] = date_to

    if data.get("rows") and not data.get("warning"):
        rows_list = list(data["rows"])
        data["rows"] = rows_list
        data["chart_config"] = json.dumps(_chart_profesionales(rows_list))
    elif not data.get("warning"):
        data["rows"] = []

    return data


def _prepare_cancelaciones_data(user, date_from, date_to):
    """Fetch and prepare cancelaciones widget data with chart config."""
    data = get_cancelaciones_report(user, date_from, date_to)
    data["date_from"] = date_from
    data["date_to"] = date_to

    if data.get("reasons") and not data.get("warning"):
        reasons_list = list(data["reasons"])
        data["reasons"] = reasons_list
        if data["cancelled"] > 0:
            data["chart_config"] = json.dumps(_chart_cancelaciones(reasons_list))
    elif not data.get("warning"):
        data["reasons"] = []

    return data


def _prepare_recursos_data(user, date_from, date_to):
    """Fetch and prepare recursos widget data with chart config."""
    data = get_recursos_report(user, date_from, date_to)
    data["date_from"] = date_from
    data["date_to"] = date_to

    if data.get("rows") and not data.get("warning"):
        rows_list = list(data["rows"])
        data["rows"] = rows_list
        data["chart_config"] = json.dumps(_chart_recursos(rows_list))
    elif not data.get("warning"):
        data["rows"] = []

    return data


def _prepare_tendencia_data(user, date_from, date_to):
    """Fetch and prepare tendencia widget data with chart config."""
    data = get_tendencia_report(user, date_from, date_to)
    data["date_from"] = date_from
    data["date_to"] = date_to

    if data.get("labels") and not data.get("warning"):
        data["chart_config"] = json.dumps(_chart_tendencia(data["labels"], data["data"]))
        data["data_zipped"] = list(zip(data["labels"], data["data"]))

    return data


def _prepare_frecuentes_data(user, date_from, date_to):
    """Fetch and prepare frecuentes widget data (table only, no chart)."""
    data = get_frecuentes_report(user, date_from, date_to)
    data["date_from"] = date_from
    data["date_to"] = date_to

    if data.get("rows") and not data.get("warning"):
        data["rows"] = list(data["rows"])
    elif not data.get("warning"):
        data["rows"] = []

    return data


def _prepare_horas_pico_data(user, date_from, date_to):
    """Fetch and prepare horas pico widget data with chart config."""
    data = get_horas_pico_report(user, date_from, date_to)
    data["date_from"] = date_from
    data["date_to"] = date_to

    if data.get("rows") and not data.get("warning"):
        data["chart_config"] = json.dumps(_chart_horas_pico(data["rows"]))

    return data


@login_required
def widget_profesionales(request):
    """HTMX partial endpoint: profesionales widget."""
    date_from = _validate_date_or_400(request.GET.get("date_from"), "Fecha desde")
    if isinstance(date_from, HttpResponseBadRequest):
        return date_from
    date_to = _validate_date_or_400(request.GET.get("date_to"), "Fecha hasta")
    if isinstance(date_to, HttpResponseBadRequest):
        return date_to
    data = _prepare_profesionales_data(request.user, date_from, date_to)
    return render(request, "reports/partials/profesionales.html", data)


@login_required
def widget_cancelaciones(request):
    """HTMX partial endpoint: cancelaciones widget."""
    date_from = _validate_date_or_400(request.GET.get("date_from"), "Fecha desde")
    if isinstance(date_from, HttpResponseBadRequest):
        return date_from
    date_to = _validate_date_or_400(request.GET.get("date_to"), "Fecha hasta")
    if isinstance(date_to, HttpResponseBadRequest):
        return date_to
    data = _prepare_cancelaciones_data(request.user, date_from, date_to)
    return render(request, "reports/partials/cancelaciones.html", data)


@login_required
def widget_recursos(request):
    """HTMX partial endpoint: recursos widget."""
    date_from = _validate_date_or_400(request.GET.get("date_from"), "Fecha desde")
    if isinstance(date_from, HttpResponseBadRequest):
        return date_from
    date_to = _validate_date_or_400(request.GET.get("date_to"), "Fecha hasta")
    if isinstance(date_to, HttpResponseBadRequest):
        return date_to
    data = _prepare_recursos_data(request.user, date_from, date_to)
    return render(request, "reports/partials/recursos.html", data)


@login_required
def widget_tendencia(request):
    """HTMX partial endpoint: tendencia widget."""
    date_from = _validate_date_or_400(request.GET.get("date_from"), "Fecha desde")
    if isinstance(date_from, HttpResponseBadRequest):
        return date_from
    date_to = _validate_date_or_400(request.GET.get("date_to"), "Fecha hasta")
    if isinstance(date_to, HttpResponseBadRequest):
        return date_to
    data = _prepare_tendencia_data(request.user, date_from, date_to)
    return render(request, "reports/partials/tendencia.html", data)


@login_required
def widget_frecuentes(request):
    """HTMX partial endpoint: frecuentes widget."""
    date_from = _validate_date_or_400(request.GET.get("date_from"), "Fecha desde")
    if isinstance(date_from, HttpResponseBadRequest):
        return date_from
    date_to = _validate_date_or_400(request.GET.get("date_to"), "Fecha hasta")
    if isinstance(date_to, HttpResponseBadRequest):
        return date_to
    data = _prepare_frecuentes_data(request.user, date_from, date_to)
    return render(request, "reports/partials/frecuentes.html", data)


@login_required
def widget_horas_pico(request):
    """HTMX partial endpoint: horas pico widget."""
    date_from = _validate_date_or_400(request.GET.get("date_from"), "Fecha desde")
    if isinstance(date_from, HttpResponseBadRequest):
        return date_from
    date_to = _validate_date_or_400(request.GET.get("date_to"), "Fecha hasta")
    if isinstance(date_to, HttpResponseBadRequest):
        return date_to
    data = _prepare_horas_pico_data(request.user, date_from, date_to)
    return render(request, "reports/partials/horas_pico.html", data)


# ── CSV export views ───────────────────────────────────────────────────


@login_required
def csv_profesionales(request):
    """CSV export: profesionales report."""
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")
    data = get_profesionales_report(request.user, date_from, date_to)
    headers = [
        "Profesional",
        "Programados",
        "Confirmados",
        "Llegó",
        "Atención",
        "Completados",
        "Cancelados",
        "Total",
    ]
    rows = [
        [
            f"{r['professional__last_name']}, {r['professional__first_name']}",
            r["scheduled"],
            r["confirmed"],
            r["arrived"],
            r["in_progress"],
            r["completed"],
            r["cancelled"],
            r["total"],
        ]
        for r in data.get("rows", [])
    ]
    return csv_response(rows, headers, f"profesionales_{date_from}_{date_to}.csv")


@login_required
def csv_cancelaciones(request):
    """CSV export: cancelaciones report."""
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")
    data = get_cancelaciones_report(request.user, date_from, date_to)
    headers = ["Motivo", "Cantidad"]
    rows = [[r["cancellation_reason"] or "Sin motivo", r["count"]] for r in data.get("reasons", [])]
    return csv_response(rows, headers, f"cancelaciones_{date_from}_{date_to}.csv")


@login_required
def csv_recursos(request):
    """CSV export: recursos report."""
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")
    data = get_recursos_report(request.user, date_from, date_to)
    headers = ["Recurso", "Total Turnos"]
    rows = [[r["resource__name"], r["total"]] for r in data.get("rows", [])]
    return csv_response(rows, headers, f"recursos_{date_from}_{date_to}.csv")


@login_required
def csv_tendencia(request):
    """CSV export: tendencia report."""
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")
    data = get_tendencia_report(request.user, date_from, date_to)
    headers = ["Período", "Cantidad"]
    rows = list(zip(data.get("labels", []), data.get("data", [])))
    return csv_response(rows, headers, f"tendencia_{date_from}_{date_to}.csv")


@login_required
def csv_frecuentes(request):
    """CSV export: pacientes frecuentes report."""
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")
    data = get_frecuentes_report(request.user, date_from, date_to)
    headers = ["Paciente", "DNI", "Turnos", "Última Visita"]
    rows = [
        [
            r["patient_name"],
            r["patient_dni"],
            r["count"],
            r["last_date"].isoformat() if r.get("last_date") else "",
        ]
        for r in data.get("rows", [])
    ]
    return csv_response(rows, headers, f"frecuentes_{date_from}_{date_to}.csv")


@login_required
def csv_horas_pico(request):
    """CSV export: horas pico report."""
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")
    data = get_horas_pico_report(request.user, date_from, date_to)
    headers = ["Horario", "Turnos"]
    rows = [[r["label"], r["total"]] for r in data.get("rows", [])]
    return csv_response(rows, headers, f"horas_pico_{date_from}_{date_to}.csv")
