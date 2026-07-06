from django.contrib import admin

from .models import Fortune, FortuneSet


@admin.register(FortuneSet)
class FortuneSetAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_default", "is_public", "is_active", "updated_at")
    list_filter = ("is_default", "is_public", "is_active")
    search_fields = ("code", "name", "source_name")


@admin.register(Fortune)
class FortuneAdmin(admin.ModelAdmin):
    list_display = ("fortune_set", "number", "title", "fortune_level", "is_active", "updated_at")
    list_filter = ("fortune_set", "fortune_level", "is_active")
    search_fields = ("title", "poem", "translation", "story")
