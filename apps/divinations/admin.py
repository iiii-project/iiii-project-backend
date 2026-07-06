from django.contrib import admin

from .models import BlockCast, DivinationSession


class BlockCastInline(admin.TabularInline):
    model = BlockCast
    extra = 0
    readonly_fields = ("attempt_number", "block_one", "block_two", "result", "created_at")


@admin.register(DivinationSession)
class DivinationSessionAdmin(admin.ModelAdmin):
    list_display = ("session_uuid", "category", "status", "confirmed", "fortune", "created_at")
    list_filter = ("category", "interaction_mode", "status", "confirmed")
    search_fields = ("session_uuid", "anonymous_user_id", "question")
    inlines = [BlockCastInline]


@admin.register(BlockCast)
class BlockCastAdmin(admin.ModelAdmin):
    list_display = ("divination_session", "attempt_number", "block_one", "block_two", "result", "created_at")
    list_filter = ("result", "created_at")
