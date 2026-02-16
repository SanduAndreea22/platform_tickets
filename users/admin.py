from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser

    list_display = ("username", "email", "is_participant", "is_organizer", "is_staff", "is_active")
    list_filter = ("is_participant", "is_organizer", "is_staff", "is_active")

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Informații personale", {"fields": ("first_name", "last_name", "email")}),
        ("Roluri", {"fields": ("is_participant", "is_organizer")}),
        ("Permisiuni", {"fields": ("is_staff", "is_active", "is_superuser", "groups", "user_permissions")}),
        ("Date importante", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "email", "password1", "password2", "is_participant", "is_organizer", "is_staff", "is_active"),
        }),
    )

    search_fields = ("username", "email")
    ordering = ("username",)

