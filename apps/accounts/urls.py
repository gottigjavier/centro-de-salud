from django.urls import path
from django.views.generic.base import RedirectView

from . import views

app_name = "accounts"

urlpatterns = [
    # Override allauth's signup — el registro público no está habilitado
    path(
        "signup/",
        RedirectView.as_view(pattern_name="account_login", permanent=False),
        name="account_signup",
    ),
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
