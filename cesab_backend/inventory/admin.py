from django.contrib import admin
from .models import InventoryItem, InventoryMovement


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ["name", "unit", "project", "is_active"]
    list_filter = ["project", "is_active"]
    search_fields = ["name"]


@admin.register(InventoryMovement)
class InventoryMovementAdmin(admin.ModelAdmin):
    list_display = ["item", "movement_type", "quantity", "unit_cost", "total_cost", "created_at"]
    list_filter = ["movement_type", "project"]
    readonly_fields = ["created_at"]
