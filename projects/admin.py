from django.contrib import admin
from .models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ["name", "base_currency", "is_active", "created_at"]
    list_filter = ["is_active", "base_currency"]
    search_fields = ["name"]
