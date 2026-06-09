from django.urls import path

from . import views

app_name = "appointments"

urlpatterns = [
    path("", views.CalendarView.as_view(), name="calendar"),
    path("lista/", views.AppointmentListView.as_view(), name="list"),
]
