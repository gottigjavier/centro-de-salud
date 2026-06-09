from django.contrib import admin

from .models import NonWorkingDay, Resource, ResourceSchedule


@admin.register(NonWorkingDay)
class NonWorkingDayAdmin(admin.ModelAdmin):
    list_display = ["date", "reason", "is_recurring", "is_active", "created_at"]
    list_filter = ["is_recurring", "is_active"]
    search_fields = ["reason", "date"]
    date_hierarchy = "date"


class ResourceScheduleInline(admin.TabularInline):
    model = ResourceSchedule
    extra = 1


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ("name", "type", "location", "max_capacity", "is_active")
    list_filter = ("type", "is_active")
    search_fields = ("name", "location")
    inlines = [ResourceScheduleInline]


@admin.register(ResourceSchedule)
class ResourceScheduleAdmin(admin.ModelAdmin):
    list_display = [
        "resource", "day_of_week_display", "start_time", "end_time",
        "slot_duration", "max_appointments_per_slot", "is_active",
    ]
    list_filter = ["resource", "day_of_week", "is_active"]
    search_fields = ["resource__name"]

    def day_of_week_display(self, obj):
        return dict(obj.DAYS_OF_WEEK).get(obj.day_of_week, "")
    day_of_week_display.short_description = "día"
