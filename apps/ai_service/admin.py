from django.contrib import admin

from .models import AIMessage


@admin.register(AIMessage)
class AIMessageAdmin(admin.ModelAdmin):
    list_display = ("divination_session", "role", "model_name", "created_at")
    list_filter = ("role", "model_name", "created_at")
    search_fields = ("content", "divination_session__session_uuid")
