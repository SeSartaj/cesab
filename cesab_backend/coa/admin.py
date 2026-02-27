from django.contrib import admin
from .models import Account


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "account_type", "project", "parent", "is_active"]
    list_filter = ["account_type", "is_active", "project"]
    search_fields = ["code", "name"]
    raw_id_fields = ["parent"]
