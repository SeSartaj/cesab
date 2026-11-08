from django.contrib import admin
from .models import JournalEntry, JournalLine


class JournalLineInline(admin.TabularInline):
    model = JournalLine
    extra = 2
    fields = ["account", "debit", "credit", "transaction_currency", "exchange_rate", "debit_tc", "credit_tc", "description"]


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ["__str__", "date", "project", "transaction_type", "description", "created_by", "created_at"]
    list_filter = ["transaction_type", "project", "date"]
    search_fields = ["description", "reference"]
    inlines = [JournalLineInline]
    readonly_fields = ["created_by", "created_at"]

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
