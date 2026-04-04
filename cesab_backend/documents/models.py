"""
Document layer — loosely coupled with the accounting layer.

Flow:
  1. User creates a document (DRAFT) — editable, no journal impact.
  2. User posts the document (POSTED) — a JournalEntry is created.
     A posted document cannot be edited.
  3. User reverses the document — a mirror POSTED reversal document is
     created and both journal entries cancel each other out.

Supported documents:
  - VendorBill      : bill received from a vendor (A/P)
  - CustomerInvoice : invoice issued to a customer (A/R)
  - Payment         : payment to a vendor (reduces A/P)
  - Receipt         : receipt from a customer (reduces A/R)

Multi-currency:
  Each document has a *currency* and an *exchange_rate* (base-currency
  units per 1 document-currency unit).  Lines are expressed in the
  document currency; the journal entry books both TC and BC amounts.

Tax:
  Each line can optionally reference a Tax.  Tax is computed as
  line.subtotal × tax.rate and posted to tax.account.
"""
from decimal import Decimal
from django.db import models
from django.utils.translation import gettext_lazy as _


class Tax(models.Model):
    """Simple per-project tax configuration (e.g. VAT 10%, WHT 5%)."""

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE,
        related_name="taxes", verbose_name=_("Project")
    )
    name = models.CharField(max_length=100, verbose_name=_("Name"))
    rate = models.DecimalField(
        max_digits=7, decimal_places=4,
        verbose_name=_("Rate"),
        help_text=_("Decimal rate, e.g. 0.1000 for 10 %"),
    )
    account = models.ForeignKey(
        "coa.Account", on_delete=models.PROTECT,
        related_name="tax_accounts", verbose_name=_("Tax Account"),
        help_text=_("Account to post collected/paid tax amounts to"),
    )
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))

    class Meta:
        verbose_name = _("Tax")
        verbose_name_plural = _("Taxes")
        ordering = ["name"]
        unique_together = ("project", "name")

    def __str__(self):
        return f"{self.name} ({self.rate * 100:.2f} %)"

    def rate_percent(self):
        return self.rate * 100


# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

DRAFT = "draft"
POSTED = "posted"

STATUS_CHOICES = [
    (DRAFT, _("Draft")),
    (POSTED, _("Posted")),
]


# ---------------------------------------------------------------------------
# Vendor Bill
# ---------------------------------------------------------------------------

class VendorBill(models.Model):
    """A bill received from a vendor — creates an Accounts Payable entry."""

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE,
        related_name="vendor_bills", verbose_name=_("Project")
    )
    number = models.CharField(
        max_length=50, blank=True, verbose_name=_("Number"),
        help_text=_("Auto-generated on save if left blank"),
    )
    contact = models.ForeignKey(
        "vendors.Contact", on_delete=models.PROTECT,
        related_name="vendor_bills", verbose_name=_("Vendor"),
        limit_choices_to={"contact_type__in": ["vendor", "both"]},
    )
    date = models.DateField(verbose_name=_("Bill Date"))
    due_date = models.DateField(null=True, blank=True, verbose_name=_("Due Date"))
    currency = models.ForeignKey(
        "core.Currency", on_delete=models.PROTECT,
        verbose_name=_("Currency"),
    )
    exchange_rate = models.DecimalField(
        max_digits=18, decimal_places=6, default=Decimal("1"),
        verbose_name=_("Exchange Rate"),
        help_text=_("Base-currency units per 1 unit of the document currency"),
    )
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=DRAFT,
        verbose_name=_("Status"),
    )
    notes = models.TextField(blank=True, verbose_name=_("Notes"))
    journal_entry = models.OneToOneField(
        "journal.JournalEntry", null=True, blank=True,
        on_delete=models.PROTECT, related_name="vendor_bill",
        verbose_name=_("Journal Entry"),
    )
    reversal_of = models.OneToOneField(
        "self", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="reversed_by", verbose_name=_("Reversal Of"),
    )
    created_by = models.ForeignKey(
        "auth_users.User", on_delete=models.PROTECT,
        verbose_name=_("Created By"),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Vendor Bill")
        verbose_name_plural = _("Vendor Bills")
        ordering = ["-date", "-id"]

    def __str__(self):
        return self.number or f"BILL-{self.pk}"

    def save(self, *args, **kwargs):
        if not self.number:
            super().save(*args, **kwargs)
            self.number = f"BILL-{self.pk:04d}"
            VendorBill.objects.filter(pk=self.pk).update(number=self.number)
        else:
            super().save(*args, **kwargs)

    @property
    def is_posted(self):
        return self.status == POSTED

    @property
    def is_draft(self):
        return self.status == DRAFT

    @property
    def is_reversed(self):
        return hasattr(self, "reversed_by") and self.reversed_by is not None

    def total_subtotal(self):
        return sum(l.subtotal() for l in self.lines.all())

    def total_tax(self):
        return sum(l.tax_amount() for l in self.lines.all())

    def total_amount(self):
        return self.total_subtotal() + self.total_tax()

    def total_in_base(self):
        return (self.total_amount() * self.exchange_rate).quantize(Decimal("0.01"))

    def _active_payments(self):
        """Posted payments that have not been reversed and are not themselves reversals."""
        return Payment.objects.filter(
            bill=self, status=POSTED,
            reversal_of__isnull=True,
        ).filter(reversed_by__isnull=True)

    def paid_bc(self):
        """Base-currency total of active posted payments linked to this bill."""
        base_id = self.project.base_currency_id
        total = Decimal("0")
        for pay in self._active_payments():
            if pay.currency_id == base_id:
                # Payment is already expressed in base currency
                total += pay.amount
            else:
                total += (pay.amount * pay.exchange_rate).quantize(Decimal("0.01"))
        return total.quantize(Decimal("0.01"))

    def paid_tc(self):
        """Transaction-currency total paid against this bill.

        - Same currency as bill  → use TC directly.
        - Base currency payment  → TC = amount_BC / rate (BC per TC).
        - Other foreign currency → convert BC then re-express at bill rate.
        """
        bill_currency_id = self.currency_id
        base_id = self.project.base_currency_id
        total = Decimal("0")
        for pay in self._active_payments():
            if pay.currency_id == bill_currency_id:
                total += pay.amount
            elif pay.currency_id == base_id and pay.exchange_rate:
                # Base currency paying foreign bill:
                # exchange_rate holds today's BC-per-TC rate, so TC = amount / rate
                total += (pay.amount / pay.exchange_rate).quantize(Decimal("0.01"))
            elif self.exchange_rate:
                pay_bc = (pay.amount * pay.exchange_rate).quantize(Decimal("0.01"))
                total += (pay_bc / self.exchange_rate).quantize(Decimal("0.01"))
        return total.quantize(Decimal("0.01"))

    def balance_bc(self):
        if self.is_reversed:
            return Decimal("0")
        return (self.total_in_base() - self.paid_bc()).quantize(Decimal("0.01"))

    def balance_tc(self):
        if self.is_reversed:
            return Decimal("0")
        return (self.total_amount() - self.paid_tc()).quantize(Decimal("0.01"))

    @property
    def is_overdue(self):
        from django.utils import timezone
        if not self.due_date or self.status != POSTED or self.is_reversed:
            return False
        return self.due_date < timezone.now().date()


class VendorBillLine(models.Model):
    bill = models.ForeignKey(
        VendorBill, on_delete=models.CASCADE,
        related_name="lines", verbose_name=_("Bill"),
    )
    description = models.CharField(max_length=300, blank=True, verbose_name=_("Description"))
    account = models.ForeignKey(
        "coa.Account", on_delete=models.PROTECT,
        verbose_name=_("Expense Account"),
    )
    quantity = models.DecimalField(
        max_digits=18, decimal_places=4, default=Decimal("1"),
        verbose_name=_("Quantity"),
    )
    unit_price = models.DecimalField(
        max_digits=18, decimal_places=2, verbose_name=_("Unit Price"),
    )
    tax = models.ForeignKey(
        Tax, null=True, blank=True, on_delete=models.PROTECT,
        verbose_name=_("Tax"),
    )

    class Meta:
        verbose_name = _("Bill Line")
        verbose_name_plural = _("Bill Lines")

    def subtotal(self):
        return (self.quantity * self.unit_price).quantize(Decimal("0.01"))

    def tax_amount(self):
        if self.tax:
            return (self.subtotal() * self.tax.rate).quantize(Decimal("0.01"))
        return Decimal("0")

    def total(self):
        return self.subtotal() + self.tax_amount()


# ---------------------------------------------------------------------------
# Customer Invoice
# ---------------------------------------------------------------------------

class CustomerInvoice(models.Model):
    """An invoice issued to a customer — creates an Accounts Receivable entry."""

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE,
        related_name="customer_invoices", verbose_name=_("Project")
    )
    number = models.CharField(
        max_length=50, blank=True, verbose_name=_("Number"),
    )
    contact = models.ForeignKey(
        "vendors.Contact", on_delete=models.PROTECT,
        related_name="customer_invoices", verbose_name=_("Customer"),
        limit_choices_to={"contact_type__in": ["customer", "both"]},
    )
    date = models.DateField(verbose_name=_("Invoice Date"))
    due_date = models.DateField(null=True, blank=True, verbose_name=_("Due Date"))
    currency = models.ForeignKey(
        "core.Currency", on_delete=models.PROTECT,
        verbose_name=_("Currency"),
    )
    exchange_rate = models.DecimalField(
        max_digits=18, decimal_places=6, default=Decimal("1"),
        verbose_name=_("Exchange Rate"),
        help_text=_("Base-currency units per 1 unit of the document currency"),
    )
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=DRAFT,
        verbose_name=_("Status"),
    )
    notes = models.TextField(blank=True, verbose_name=_("Notes"))
    journal_entry = models.OneToOneField(
        "journal.JournalEntry", null=True, blank=True,
        on_delete=models.PROTECT, related_name="customer_invoice",
        verbose_name=_("Journal Entry"),
    )
    reversal_of = models.OneToOneField(
        "self", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="reversed_by", verbose_name=_("Reversal Of"),
    )
    created_by = models.ForeignKey(
        "auth_users.User", on_delete=models.PROTECT,
        verbose_name=_("Created By"),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Customer Invoice")
        verbose_name_plural = _("Customer Invoices")
        ordering = ["-date", "-id"]

    def __str__(self):
        return self.number or f"INV-{self.pk}"

    def save(self, *args, **kwargs):
        if not self.number:
            super().save(*args, **kwargs)
            self.number = f"INV-{self.pk:04d}"
            CustomerInvoice.objects.filter(pk=self.pk).update(number=self.number)
        else:
            super().save(*args, **kwargs)

    @property
    def is_posted(self):
        return self.status == POSTED

    @property
    def is_draft(self):
        return self.status == DRAFT

    @property
    def is_reversed(self):
        return hasattr(self, "reversed_by") and self.reversed_by is not None

    def total_subtotal(self):
        return sum(l.subtotal() for l in self.lines.all())

    def total_tax(self):
        return sum(l.tax_amount() for l in self.lines.all())

    def total_amount(self):
        return self.total_subtotal() + self.total_tax()

    def total_in_base(self):
        return (self.total_amount() * self.exchange_rate).quantize(Decimal("0.01"))

    def _active_receipts(self):
        """Posted receipts that have not been reversed and are not themselves reversals."""
        return Receipt.objects.filter(
            invoice=self, status=POSTED,
            reversal_of__isnull=True,
        ).filter(reversed_by__isnull=True)

    def received_bc(self):
        """Base-currency total of active posted receipts linked to this invoice."""
        base_id = self.project.base_currency_id
        total = Decimal("0")
        for rec in self._active_receipts():
            if rec.currency_id == base_id:
                # Receipt is already expressed in base currency
                total += rec.amount
            else:
                total += (rec.amount * rec.exchange_rate).quantize(Decimal("0.01"))
        return total.quantize(Decimal("0.01"))

    def received_tc(self):
        """Transaction-currency total received against this invoice.

        - Same currency as invoice → use TC directly.
        - Base currency receipt   → TC = amount_BC / rate (BC per TC).
        - Other foreign currency  → convert BC then re-express at invoice rate.
        """
        inv_currency_id = self.currency_id
        base_id = self.project.base_currency_id
        total = Decimal("0")
        for rec in self._active_receipts():
            if rec.currency_id == inv_currency_id:
                total += rec.amount
            elif rec.currency_id == base_id and rec.exchange_rate:
                # Base currency received against foreign invoice:
                # exchange_rate holds today's BC-per-TC rate, so TC = amount / rate
                total += (rec.amount / rec.exchange_rate).quantize(Decimal("0.01"))
            elif self.exchange_rate:
                rec_bc = (rec.amount * rec.exchange_rate).quantize(Decimal("0.01"))
                total += (rec_bc / self.exchange_rate).quantize(Decimal("0.01"))
        return total.quantize(Decimal("0.01"))

    def balance_bc(self):
        if self.is_reversed:
            return Decimal("0")
        return (self.total_in_base() - self.received_bc()).quantize(Decimal("0.01"))

    def balance_tc(self):
        if self.is_reversed:
            return Decimal("0")
        return (self.total_amount() - self.received_tc()).quantize(Decimal("0.01"))

    @property
    def is_overdue(self):
        from django.utils import timezone
        if not self.due_date or self.status != POSTED or self.is_reversed:
            return False
        return self.due_date < timezone.now().date()


class CustomerInvoiceLine(models.Model):
    invoice = models.ForeignKey(
        CustomerInvoice, on_delete=models.CASCADE,
        related_name="lines", verbose_name=_("Invoice"),
    )
    description = models.CharField(max_length=300, blank=True, verbose_name=_("Description"))
    account = models.ForeignKey(
        "coa.Account", on_delete=models.PROTECT,
        verbose_name=_("Revenue Account"),
    )
    quantity = models.DecimalField(
        max_digits=18, decimal_places=4, default=Decimal("1"),
        verbose_name=_("Quantity"),
    )
    unit_price = models.DecimalField(
        max_digits=18, decimal_places=2, verbose_name=_("Unit Price"),
    )
    tax = models.ForeignKey(
        Tax, null=True, blank=True, on_delete=models.PROTECT,
        verbose_name=_("Tax"),
    )

    class Meta:
        verbose_name = _("Invoice Line")
        verbose_name_plural = _("Invoice Lines")

    def subtotal(self):
        return (self.quantity * self.unit_price).quantize(Decimal("0.01"))

    def tax_amount(self):
        if self.tax:
            return (self.subtotal() * self.tax.rate).quantize(Decimal("0.01"))
        return Decimal("0")

    def total(self):
        return self.subtotal() + self.tax_amount()


# ---------------------------------------------------------------------------
# Payment  (vendor → we pay them)
# ---------------------------------------------------------------------------

class Payment(models.Model):
    """Payment made to a vendor — reduces Accounts Payable."""

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE,
        related_name="vendor_payments", verbose_name=_("Project")
    )
    number = models.CharField(max_length=50, blank=True, verbose_name=_("Number"))
    contact = models.ForeignKey(
        "vendors.Contact", on_delete=models.PROTECT,
        related_name="vendor_payments", verbose_name=_("Vendor"),
        limit_choices_to={"contact_type__in": ["vendor", "both"]},
    )
    date = models.DateField(verbose_name=_("Date"))
    currency = models.ForeignKey(
        "core.Currency", on_delete=models.PROTECT,
        verbose_name=_("Currency"),
    )
    exchange_rate = models.DecimalField(
        max_digits=18, decimal_places=6, default=Decimal("1"),
        verbose_name=_("Exchange Rate"),
    )
    amount = models.DecimalField(
        max_digits=18, decimal_places=2,
        verbose_name=_("Amount"),
        help_text=_("Amount in the document currency"),
    )
    cashbox = models.ForeignKey(
        "cash.Cashbox", on_delete=models.PROTECT,
        verbose_name=_("Paid From"),
    )
    bill = models.ForeignKey(
        VendorBill, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="payments", verbose_name=_("Bill"),
        help_text=_("Optional — link to a specific bill"),
    )
    notes = models.TextField(blank=True, verbose_name=_("Notes"))
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=DRAFT,
        verbose_name=_("Status"),
    )
    journal_entry = models.OneToOneField(
        "journal.JournalEntry", null=True, blank=True,
        on_delete=models.PROTECT, related_name="vendor_payment",
        verbose_name=_("Journal Entry"),
    )
    reversal_of = models.OneToOneField(
        "self", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="reversed_by", verbose_name=_("Reversal Of"),
    )
    created_by = models.ForeignKey(
        "auth_users.User", on_delete=models.PROTECT,
        verbose_name=_("Created By"),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Payment")
        verbose_name_plural = _("Payments")
        ordering = ["-date", "-id"]

    def __str__(self):
        return self.number or f"PAY-{self.pk}"

    def save(self, *args, **kwargs):
        if not self.number:
            super().save(*args, **kwargs)
            self.number = f"PAY-{self.pk:04d}"
            Payment.objects.filter(pk=self.pk).update(number=self.number)
        else:
            super().save(*args, **kwargs)

    @property
    def is_posted(self):
        return self.status == POSTED

    @property
    def is_draft(self):
        return self.status == DRAFT

    @property
    def is_reversed(self):
        return hasattr(self, "reversed_by") and self.reversed_by is not None

    def amount_in_base(self):
        return (self.amount * self.exchange_rate).quantize(Decimal("0.01"))


# ---------------------------------------------------------------------------
# Receipt  (customer → they pay us)
# ---------------------------------------------------------------------------

class Receipt(models.Model):
    """Receipt from a customer — reduces Accounts Receivable."""

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE,
        related_name="customer_receipts", verbose_name=_("Project")
    )
    number = models.CharField(max_length=50, blank=True, verbose_name=_("Number"))
    contact = models.ForeignKey(
        "vendors.Contact", null=True, blank=True, on_delete=models.PROTECT,
        related_name="customer_receipts", verbose_name=_("Customer"),
        limit_choices_to={"contact_type__in": ["customer", "both"]},
    )
    income_account = models.ForeignKey(
        "coa.Account", null=True, blank=True, on_delete=models.PROTECT,
        related_name="walk_in_receipts", verbose_name=_("Income Account"),
        help_text=_("Used when no customer contact is selected (walk-in / one-time payment)"),
    )
    date = models.DateField(verbose_name=_("Date"))
    currency = models.ForeignKey(
        "core.Currency", on_delete=models.PROTECT,
        verbose_name=_("Currency"),
    )
    exchange_rate = models.DecimalField(
        max_digits=18, decimal_places=6, default=Decimal("1"),
        verbose_name=_("Exchange Rate"),
    )
    amount = models.DecimalField(
        max_digits=18, decimal_places=2,
        verbose_name=_("Amount"),
        help_text=_("Amount in the document currency"),
    )
    cashbox = models.ForeignKey(
        "cash.Cashbox", on_delete=models.PROTECT,
        verbose_name=_("Received Into"),
    )
    invoice = models.ForeignKey(
        CustomerInvoice, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="receipts", verbose_name=_("Invoice"),
        help_text=_("Optional — link to a specific invoice"),
    )
    notes = models.TextField(blank=True, verbose_name=_("Notes"))
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=DRAFT,
        verbose_name=_("Status"),
    )
    journal_entry = models.OneToOneField(
        "journal.JournalEntry", null=True, blank=True,
        on_delete=models.PROTECT, related_name="customer_receipt",
        verbose_name=_("Journal Entry"),
    )
    reversal_of = models.OneToOneField(
        "self", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="reversed_by", verbose_name=_("Reversal Of"),
    )
    created_by = models.ForeignKey(
        "auth_users.User", on_delete=models.PROTECT,
        verbose_name=_("Created By"),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Receipt")
        verbose_name_plural = _("Receipts")
        ordering = ["-date", "-id"]

    def __str__(self):
        return self.number or f"REC-{self.pk}"

    def save(self, *args, **kwargs):
        if not self.number:
            super().save(*args, **kwargs)
            self.number = f"REC-{self.pk:04d}"
            Receipt.objects.filter(pk=self.pk).update(number=self.number)
        else:
            super().save(*args, **kwargs)

    @property
    def is_posted(self):
        return self.status == POSTED

    @property
    def is_draft(self):
        return self.status == DRAFT

    @property
    def is_reversed(self):
        return hasattr(self, "reversed_by") and self.reversed_by is not None

    def amount_in_base(self):
        return (self.amount * self.exchange_rate).quantize(Decimal("0.01"))


# ── Attachments ─────────────────────────────────────────────────────────────

_ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp"}


def _bill_upload_path(instance, filename):
    return f"documents/bills/{instance.bill_id}/{filename}"


def _invoice_upload_path(instance, filename):
    return f"documents/invoices/{instance.invoice_id}/{filename}"


class VendorBillAttachment(models.Model):
    bill = models.ForeignKey(
        VendorBill, on_delete=models.CASCADE, related_name="attachments"
    )
    file = models.FileField(upload_to=_bill_upload_path)
    original_name = models.CharField(max_length=255)
    uploaded_by = models.ForeignKey(
        "auth_users.User", on_delete=models.PROTECT, related_name="+"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.original_name


class CustomerInvoiceAttachment(models.Model):
    invoice = models.ForeignKey(
        CustomerInvoice, on_delete=models.CASCADE, related_name="attachments"
    )
    file = models.FileField(upload_to=_invoice_upload_path)
    original_name = models.CharField(max_length=255)
    uploaded_by = models.ForeignKey(
        "auth_users.User", on_delete=models.PROTECT, related_name="+"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.original_name
