import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("coa", "0001_initial"),
        ("core", "0001_initial"),
        ("projects", "0001_initial"),
        ("vendors", "0001_initial"),
        ("cash", "0001_initial"),
        ("journal", "0002_journalentry_corrects_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Tax
        migrations.CreateModel(
            name="Tax",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100, verbose_name="Name")),
                ("rate", models.DecimalField(decimal_places=4, help_text="Decimal rate, e.g. 0.1000 for 10 %", max_digits=7, verbose_name="Rate")),
                ("is_active", models.BooleanField(default=True, verbose_name="Active")),
                ("account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="tax_accounts", to="coa.account", verbose_name="Tax Account")),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="taxes", to="projects.project", verbose_name="Project")),
            ],
            options={"verbose_name": "Tax", "verbose_name_plural": "Taxes", "ordering": ["name"], "unique_together": {("project", "name")}},
        ),

        # VendorBill
        migrations.CreateModel(
            name="VendorBill",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("number", models.CharField(blank=True, max_length=50, verbose_name="Number")),
                ("date", models.DateField(verbose_name="Bill Date")),
                ("due_date", models.DateField(blank=True, null=True, verbose_name="Due Date")),
                ("exchange_rate", models.DecimalField(decimal_places=6, default=Decimal("1"), max_digits=18, verbose_name="Exchange Rate")),
                ("status", models.CharField(choices=[("draft", "Draft"), ("posted", "Posted")], default="draft", max_length=10, verbose_name="Status")),
                ("notes", models.TextField(blank=True, verbose_name="Notes")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("contact", models.ForeignKey(limit_choices_to={"contact_type__in": ["vendor", "both"]}, on_delete=django.db.models.deletion.PROTECT, related_name="vendor_bills", to="vendors.contact", verbose_name="Vendor")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL, verbose_name="Created By")),
                ("currency", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="core.currency", verbose_name="Currency")),
                ("journal_entry", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="vendor_bill", to="journal.journalentry", verbose_name="Journal Entry")),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="vendor_bills", to="projects.project", verbose_name="Project")),
                ("reversal_of", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reversed_by", to="documents.vendorbill", verbose_name="Reversal Of")),
            ],
            options={"verbose_name": "Vendor Bill", "verbose_name_plural": "Vendor Bills", "ordering": ["-date", "-id"]},
        ),

        # VendorBillLine
        migrations.CreateModel(
            name="VendorBillLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("description", models.CharField(blank=True, max_length=300, verbose_name="Description")),
                ("quantity", models.DecimalField(decimal_places=4, default=Decimal("1"), max_digits=18, verbose_name="Quantity")),
                ("unit_price", models.DecimalField(decimal_places=2, max_digits=18, verbose_name="Unit Price")),
                ("account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="coa.account", verbose_name="Expense Account")),
                ("bill", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lines", to="documents.vendorbill", verbose_name="Bill")),
                ("tax", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="documents.tax", verbose_name="Tax")),
            ],
            options={"verbose_name": "Bill Line", "verbose_name_plural": "Bill Lines"},
        ),

        # CustomerInvoice
        migrations.CreateModel(
            name="CustomerInvoice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("number", models.CharField(blank=True, max_length=50, verbose_name="Number")),
                ("date", models.DateField(verbose_name="Invoice Date")),
                ("due_date", models.DateField(blank=True, null=True, verbose_name="Due Date")),
                ("exchange_rate", models.DecimalField(decimal_places=6, default=Decimal("1"), max_digits=18, verbose_name="Exchange Rate")),
                ("status", models.CharField(choices=[("draft", "Draft"), ("posted", "Posted")], default="draft", max_length=10, verbose_name="Status")),
                ("notes", models.TextField(blank=True, verbose_name="Notes")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("contact", models.ForeignKey(limit_choices_to={"contact_type__in": ["customer", "both"]}, on_delete=django.db.models.deletion.PROTECT, related_name="customer_invoices", to="vendors.contact", verbose_name="Customer")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL, verbose_name="Created By")),
                ("currency", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="core.currency", verbose_name="Currency")),
                ("journal_entry", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="customer_invoice", to="journal.journalentry", verbose_name="Journal Entry")),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="customer_invoices", to="projects.project", verbose_name="Project")),
                ("reversal_of", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reversed_by", to="documents.customerinvoice", verbose_name="Reversal Of")),
            ],
            options={"verbose_name": "Customer Invoice", "verbose_name_plural": "Customer Invoices", "ordering": ["-date", "-id"]},
        ),

        # CustomerInvoiceLine
        migrations.CreateModel(
            name="CustomerInvoiceLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("description", models.CharField(blank=True, max_length=300, verbose_name="Description")),
                ("quantity", models.DecimalField(decimal_places=4, default=Decimal("1"), max_digits=18, verbose_name="Quantity")),
                ("unit_price", models.DecimalField(decimal_places=2, max_digits=18, verbose_name="Unit Price")),
                ("account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="coa.account", verbose_name="Revenue Account")),
                ("invoice", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lines", to="documents.customerinvoice", verbose_name="Invoice")),
                ("tax", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="documents.tax", verbose_name="Tax")),
            ],
            options={"verbose_name": "Invoice Line", "verbose_name_plural": "Invoice Lines"},
        ),

        # Payment
        migrations.CreateModel(
            name="Payment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("number", models.CharField(blank=True, max_length=50, verbose_name="Number")),
                ("date", models.DateField(verbose_name="Date")),
                ("exchange_rate", models.DecimalField(decimal_places=6, default=Decimal("1"), max_digits=18, verbose_name="Exchange Rate")),
                ("amount", models.DecimalField(decimal_places=2, help_text="Amount in the document currency", max_digits=18, verbose_name="Amount")),
                ("notes", models.TextField(blank=True, verbose_name="Notes")),
                ("status", models.CharField(choices=[("draft", "Draft"), ("posted", "Posted")], default="draft", max_length=10, verbose_name="Status")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("bill", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="payments", to="documents.vendorbill", verbose_name="Bill")),
                ("cashbox", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="cash.cashbox", verbose_name="Paid From")),
                ("contact", models.ForeignKey(limit_choices_to={"contact_type__in": ["vendor", "both"]}, on_delete=django.db.models.deletion.PROTECT, related_name="vendor_payments", to="vendors.contact", verbose_name="Vendor")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL, verbose_name="Created By")),
                ("currency", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="core.currency", verbose_name="Currency")),
                ("journal_entry", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="vendor_payment", to="journal.journalentry", verbose_name="Journal Entry")),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="vendor_payments", to="projects.project", verbose_name="Project")),
                ("reversal_of", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reversed_by", to="documents.payment", verbose_name="Reversal Of")),
            ],
            options={"verbose_name": "Payment", "verbose_name_plural": "Payments", "ordering": ["-date", "-id"]},
        ),

        # Receipt
        migrations.CreateModel(
            name="Receipt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("number", models.CharField(blank=True, max_length=50, verbose_name="Number")),
                ("date", models.DateField(verbose_name="Date")),
                ("exchange_rate", models.DecimalField(decimal_places=6, default=Decimal("1"), max_digits=18, verbose_name="Exchange Rate")),
                ("amount", models.DecimalField(decimal_places=2, help_text="Amount in the document currency", max_digits=18, verbose_name="Amount")),
                ("notes", models.TextField(blank=True, verbose_name="Notes")),
                ("status", models.CharField(choices=[("draft", "Draft"), ("posted", "Posted")], default="draft", max_length=10, verbose_name="Status")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("cashbox", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="cash.cashbox", verbose_name="Received Into")),
                ("contact", models.ForeignKey(limit_choices_to={"contact_type__in": ["customer", "both"]}, on_delete=django.db.models.deletion.PROTECT, related_name="customer_receipts", to="vendors.contact", verbose_name="Customer")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL, verbose_name="Created By")),
                ("currency", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="core.currency", verbose_name="Currency")),
                ("invoice", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="receipts", to="documents.customerinvoice", verbose_name="Invoice")),
                ("journal_entry", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="customer_receipt", to="journal.journalentry", verbose_name="Journal Entry")),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="customer_receipts", to="projects.project", verbose_name="Project")),
                ("reversal_of", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reversed_by", to="documents.receipt", verbose_name="Reversal Of")),
            ],
            options={"verbose_name": "Receipt", "verbose_name_plural": "Receipts", "ordering": ["-date", "-id"]},
        ),
    ]
