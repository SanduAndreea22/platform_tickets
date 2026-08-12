from django.contrib import admin

from .models import SupportMessage


@admin.register(SupportMessage)
class SupportMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "thread_id", "is_support", "created_at")
    list_filter = ("is_support", "created_at")
    search_fields = ("name", "email", "message", "response")
    readonly_fields = ("thread_id", "created_at")
