from django.contrib import admin
from .models import Partner, ProjectPartner


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = ["name", "email", "phone", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name", "email"]


@admin.register(ProjectPartner)
class ProjectPartnerAdmin(admin.ModelAdmin):
    list_display = ["partner", "project", "ownership_percent", "capital_commitment", "joined_at", "is_active"]
    list_filter = ["is_active", "project"]
    search_fields = ["partner__name", "project__name"]
