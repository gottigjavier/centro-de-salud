from django.urls import path

from . import views

app_name = "resources"

urlpatterns = [
    # ── Resource CRUD ─────────────────────────────────────────────
    path("", views.resource_list, name="list"),
    path("<int:pk>/", views.resource_detail, name="detail"),
    path("crear/", views.resource_create, name="create"),
    path("<int:pk>/editar/", views.resource_update, name="update"),
    path(
        "<int:pk>/toggle-active/",
        views.resource_toggle_active,
        name="toggle_active",
    ),
    # ── ResourceSchedule HTMX inline ───────────────────────────────
    path(
        "<int:pk>/horarios/agregar/",
        views.schedule_add,
        name="schedule_add",
    ),
    path(
        "horarios/<int:pk>/eliminar/",
        views.schedule_delete,
        name="schedule_delete",
    ),
    # ── NonWorkingDay CRUD ─────────────────────────────────────────
    path("feriados/", views.nonworkingday_list, name="nonworkingday_list"),
    path(
        "feriados/crear/",
        views.nonworkingday_create,
        name="nonworkingday_create",
    ),
    path(
        "feriados/<int:pk>/eliminar/",
        views.nonworkingday_delete,
        name="nonworkingday_delete",
    ),
]
