from django.contrib import admin

from .models import NotificationConfig, NotificationLog


@admin.register(NotificationConfig)
class NotificationConfigAdmin(admin.ModelAdmin):
    list_display = [
        "resource", "reminder_enabled", "email_enabled",
        "whatsapp_enabled", "reminder_before_minutes",
    ]
    list_filter = ["reminder_enabled", "email_enabled", "whatsapp_enabled"]


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = [
        "appointment", "channel", "notification_type",
        "recipient", "status", "sent_at", "created_at",
    ]
    list_filter = ["channel", "notification_type", "status"]
    search_fields = ["appointment__id", "recipient"]
    readonly_fields = [
        "appointment", "channel", "notification_type",
        "recipient", "status", "error_message", "sent_at", "created_at",
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
