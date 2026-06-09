from django.urls import path

from . import views

app_name = "professionals"

urlpatterns = [
    # ── Professional CRUD ─────────────────────────────────────────────
    path("", views.professional_list, name="list"),
    path("<int:pk>/", views.professional_detail, name="detail"),
    path("crear/", views.professional_create, name="create"),
    path("<int:pk>/editar/", views.professional_update, name="update"),
    path(
        "<int:pk>/toggle-active/",
        views.professional_toggle_active,
        name="toggle_active",
    ),
    # ── ProfessionalResourceAssignment HTMX inline ─────────────────────
    path(
        "<int:pk>/asignaciones/agregar/",
        views.assignment_add,
        name="assignment_add",
    ),
    path(
        "asignaciones/<int:pk>/eliminar/",
        views.assignment_delete,
        name="assignment_delete",
    ),
]
