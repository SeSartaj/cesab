from django.contrib import admin
from .models import Tax, VendorBill, VendorBillLine, CustomerInvoice, CustomerInvoiceLine, Payment, Receipt


@admin.register(Tax)
class TaxAdmin(admin.ModelAdmin):
    list_display = ["name", "project", "rate", "account", "is_active"]
    list_filter = ["project", "is_active"]


class VendorBillLineInline(admin.TabularInline):
    model = VendorBillLine
    extra = 0


@admin.register(VendorBill)
class VendorBillAdmin(admin.ModelAdmin):
    list_display = ["number", "contact", "project", "date", "status", "total_amount"]
    list_filter = ["status", "project"]
    inlines = [VendorBillLineInline]
    readonly_fields = ["journal_entry", "status"]


class CustomerInvoiceLineInline(admin.TabularInline):
    model = CustomerInvoiceLine
    extra = 0


@admin.register(CustomerInvoice)
class CustomerInvoiceAdmin(admin.ModelAdmin):
    list_display = ["number", "contact", "project", "date", "status", "total_amount"]
    list_filter = ["status", "project"]
    inlines = [CustomerInvoiceLineInline]
    readonly_fields = ["journal_entry", "status"]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["number", "contact", "project", "date", "amount", "currency", "status"]
    list_filter = ["status", "project"]
    readonly_fields = ["journal_entry", "status"]


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ["number", "contact", "project", "date", "amount", "currency", "status"]
    list_filter = ["status", "project"]
    readonly_fields = ["journal_entry", "status"]
