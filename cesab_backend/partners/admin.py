from django.contrib import admin
from .models import ProjectPartner


@admin.register(ProjectPartner)
class ProjectPartnerAdmin(admin.ModelAdmin):
    list_display = ["name", "user", "project", "ownership_percent", "capital_commitment", "joined_at", "is_active"]
    list_filter = ["is_active", "project"]
    search_fields = ["name", "user__username", "user__first_name", "user__last_name", "project__name"]
