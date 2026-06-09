from django.contrib import admin

from .models import Appointment


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = [
        "patient_name", "patient_dni", "date", "start_time", "end_time",
        "resource", "professional", "status", "created_by",
    ]
    list_filter = ["status", "date", "resource", "professional"]
    search_fields = ["patient_name", "patient_dni", "patient_phone"]
    date_hierarchy = "date"
    autocomplete_fields = ["resource", "professional", "created_by"]
    readonly_fields = ["created_at", "updated_at"]
    fieldsets = (
        ("Paciente", {
            "fields": ("patient_name", "patient_dni", "patient_phone", "patient_email")
        }),
        ("Turno", {
            "fields": ("resource", "professional", "date", "start_time", "end_time", "status")
        }),
        ("Metadatos", {
            "fields": ("comments", "created_by")
        }),
    )
