from django.contrib import admin
from .models import Cashbox


@admin.register(Cashbox)
class CashboxAdmin(admin.ModelAdmin):
    list_display = ["name", "project", "currency", "is_active"]
    list_filter = ["is_active", "project"]
    search_fields = ["name"]
