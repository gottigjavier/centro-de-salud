from django.urls import path

from . import views

app_name = "appointments"

urlpatterns = [
    # ── CRUD ────────────────────────────────────────────────────
    path("", views.calendar_view_placeholder, name="calendar"),
    path("lista/", views.appointment_list, name="list"),
    path("crear/", views.appointment_create, name="create"),
    path("<int:pk>/", views.appointment_detail, name="detail"),
    path("<int:pk>/editar/", views.appointment_update, name="update"),
    path("<int:pk>/cancelar/", views.appointment_cancel, name="cancel"),

    # ── Agenda del Día ──────────────────────────────────────────
    path("agenda/", views.agenda_view, name="agenda"),
    path("agenda/stats/", views.htmx_agenda_stats, name="agenda_stats"),
    path("agenda/table/", views.htmx_agenda_table, name="agenda_table"),

    # ── State transitions (POST only) ───────────────────────────
    path(
        "<int:pk>/transition/<str:status>/",
        views.appointment_transition,
        name="transition",
    ),

    # ── HTMX dynamic selects ────────────────────────────────────
    path(
        "htmx/profesionales-por-recurso/<int:resource_id>/",
        views.htmx_profesionales,
        name="htmx_profesionales",
    ),
    path(
        "htmx/horarios-por-profesional/<int:professional_id>/",
        views.htmx_horarios,
        name="htmx_horarios",
    ),
]
