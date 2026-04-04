from django.contrib import admin
from .models import Contact


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ["name", "project", "contact_type", "phone", "is_active"]
    list_filter = ["is_active", "contact_type", "project"]
    search_fields = ["name"]
