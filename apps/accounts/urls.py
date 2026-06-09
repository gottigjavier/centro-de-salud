from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("perfil/", views.profile, name="profile"),
    path("setup/", views.setup, name="setup"),
    path("usuarios/", views.user_list, name="user_list"),
    path("usuarios/crear/", views.user_create, name="user_create"),
    path("usuarios/<int:pk>/editar/", views.user_edit, name="user_edit"),
    path(
        "usuarios/<int:pk>/toggle-active/",
        views.user_toggle_active,
        name="user_toggle_active",
    ),
]
