from django.contrib import admin
from .models import Vendor


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ["name", "project", "phone", "is_active"]
    list_filter = ["is_active", "project"]
    search_fields = ["name"]
