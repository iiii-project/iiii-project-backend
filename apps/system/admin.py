from django.contrib import admin

from .models import SystemLog, SystemSetting


@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display = ("key", "updated_at")
    search_fields = ("key", "value", "description")


@admin.register(SystemLog)
class SystemLogAdmin(admin.ModelAdmin):
    list_display = ("level", "event_type", "request_path", "created_at")
    list_filter = ("level", "event_type", "created_at")
    search_fields = ("message", "request_path")
