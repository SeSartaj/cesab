from django.contrib import admin
from .models import ProjectEmployee


@admin.register(ProjectEmployee)
class ProjectEmployeeAdmin(admin.ModelAdmin):
    list_display = ["name", "project", "salary_type", "salary_amount", "is_active"]
    list_filter = ["is_active", "salary_type", "project"]
    search_fields = ["name"]
