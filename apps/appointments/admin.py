from django.contrib import admin
from django.utils.html import format_html

from apps.notifications.models import NotificationLog
from .models import Appointment


class NotificationLogInline(admin.TabularInline):
    model = NotificationLog
    extra = 0
    can_delete = False
    readonly_fields = ["channel", "notification_type", "recipient", "status", "error_message", "sent_at", "created_at"]
    ordering = ["-created_at"]
    max_num = 10
    show_change_link = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    inlines = [NotificationLogInline]
    list_display = [
        "patient_name", "patient_dni", "date", "start_time", "end_time",
        "resource", "professional", "status", "deleted_badge", "created_by",
    ]
    list_filter = ["status", "date", "resource", "professional"]
    search_fields = ["patient_name", "patient_dni", "patient_phone"]
    date_hierarchy = "date"
    autocomplete_fields = ["resource", "professional", "created_by"]
    readonly_fields = ["created_at", "updated_at", "deleted_at"]
    fieldsets = (
        ("Paciente", {
            "fields": ("patient_name", "patient_dni", "patient_phone", "patient_email")
        }),
        ("Turno", {
            "fields": ("resource", "professional", "date", "start_time", "end_time", "status", "send_reminder")
        }),
        ("Metadatos", {
            "fields": ("comments", "created_by", "deleted_at")
        }),
    )

    def save_model(self, request, obj, form, change):
        """Override save to enforce model-level validation (V-001..V-007)."""
        obj.full_clean()
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        qs = self.model.all_objects.get_queryset()
        if not request.GET.get("show_deleted"):
            qs = qs.filter(deleted_at__isnull=True)
        return qs

    @admin.display(description="eliminado")
    def deleted_badge(self, obj):
        if obj.deleted_at:
            return format_html(
                '<span style="color: #dc2626; font-weight: 600;">Eliminado</span>'
            )
        return ""
