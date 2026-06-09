from django.contrib import admin

from .models import Professional, ProfessionalResourceAssignment


@admin.register(Professional)
class ProfessionalAdmin(admin.ModelAdmin):
    list_display = [
        "last_name", "first_name", "specialty", "license_number",
        "phone", "is_active",
    ]
    list_filter = ["specialty", "is_active"]
    search_fields = ["last_name", "first_name", "license_number"]
    filter_horizontal = ("resources",)


@admin.register(ProfessionalResourceAssignment)
class ProfessionalResourceAssignmentAdmin(admin.ModelAdmin):
    list_display = [
        "professional", "resource", "day_of_week",
        "start_date", "end_date", "start_time", "end_time", "is_active",
    ]
    list_filter = ["professional", "resource", "day_of_week", "is_active"]
    search_fields = [
        "professional__last_name", "professional__first_name",
        "resource__name",
    ]
    date_hierarchy = "start_date"
