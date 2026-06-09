"""Views for appointment management — calendar, booking, listing."""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, TemplateView

from .models import Appointment


class CalendarView(LoginRequiredMixin, TemplateView):
    """Main calendar view with occupancy color indicators."""
    template_name = "appointments/calendar.html"


class AppointmentListView(LoginRequiredMixin, ListView):
    """List of appointments, filterable by date."""
    model = Appointment
    template_name = "appointments/appointment_list.html"
    context_object_name = "appointments"
    paginate_by = 30

    def get_queryset(self):
        qs = super().get_queryset()
        qs = qs.select_related("resource", "professional")
        return qs
