from django.urls import path

from . import views

app_name = "professionals"

urlpatterns = [
    path("", views.ProfessionalListView.as_view(), name="list"),
]
