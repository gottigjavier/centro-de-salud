"""Views for professional management."""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView

from .models import Professional


class ProfessionalListView(LoginRequiredMixin, ListView):
    model = Professional
    template_name = "professionals/professional_list.html"
    context_object_name = "professionals"
    paginate_by = 20
