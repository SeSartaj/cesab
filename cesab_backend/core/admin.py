from django.contrib import admin
from .models import Currency


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "symbol", "decimal_places", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["code", "name"]
