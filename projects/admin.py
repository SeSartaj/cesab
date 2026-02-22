from django.contrib import admin
from .models import Project, ProjectMember


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ["name", "base_currency", "is_active", "created_at"]
    list_filter = ["is_active", "base_currency"]
    search_fields = ["name"]


@admin.register(ProjectMember)
class ProjectMemberAdmin(admin.ModelAdmin):
    list_display = ["project", "user", "role"]
    list_filter = ["project", "role"]
    search_fields = ["user__username", "project__name"]
    autocomplete_fields = ["user"]
