from django.db import models
from django.utils.translation import gettext_lazy as _
from decimal import Decimal


class Contact(models.Model):
    """A vendor, customer, or both — the unified party model."""

    VENDOR = "vendor"
    CUSTOMER = "customer"
    BOTH = "both"
    TYPE_CHOICES = [
        (VENDOR, _("Vendor")),
        (CUSTOMER, _("Customer")),
        (BOTH, _("Vendor & Customer")),
    ]

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE,
        related_name="contacts", verbose_name=_("Project")
    )
    name = models.CharField(max_length=200, verbose_name=_("Name"))
    phone = models.CharField(max_length=50, blank=True, verbose_name=_("Phone"))
    contact_type = models.CharField(
        max_length=10, choices=TYPE_CHOICES, default=VENDOR,
        verbose_name=_("Type")
    )
    # Vendor-side accounts (required when contact_type is vendor or both)
    payable_account = models.ForeignKey(
        "coa.Account", null=True, blank=True, on_delete=models.PROTECT,
        related_name="contact_payable_accounts", verbose_name=_("Payable Account")
    )
    advance_account = models.ForeignKey(
        "coa.Account", null=True, blank=True, on_delete=models.PROTECT,
        related_name="contact_advance_accounts", verbose_name=_("Advance Account")
    )
    # Customer-side accounts (required when contact_type is customer or both)
    receivable_account = models.ForeignKey(
        "coa.Account", null=True, blank=True, on_delete=models.PROTECT,
        related_name="contact_receivable_accounts", verbose_name=_("Receivable Account")
    )
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))

    class Meta:
        verbose_name = _("Contact")
        verbose_name_plural = _("Contacts")
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def is_vendor(self):
        return self.contact_type in (self.VENDOR, self.BOTH)

    @property
    def is_customer(self):
        return self.contact_type in (self.CUSTOMER, self.BOTH)

    # ------------------------------------------------------------------
    # Vendor-side helpers
    # ------------------------------------------------------------------

    def balance_payable(self):
        if not self.payable_account:
            return Decimal("0")
        from journal.models import JournalLine
        lines = JournalLine.objects.active().filter(account=self.payable_account)
        return sum(l.credit for l in lines) - sum(l.debit for l in lines)

    def advance_balance(self):
        if not self.advance_account:
            return Decimal("0")
        from journal.models import JournalLine
        lines = JournalLine.objects.active().filter(account=self.advance_account)
        return sum(l.debit for l in lines) - sum(l.credit for l in lines)

    def total_paid(self):
        """Total cash ever paid to this contact as a vendor."""
        if not self.payable_account:
            return Decimal("0")
        from journal.models import JournalLine
        from inventory.models import InventoryMovement
        from django.db.models import Sum
        bill_paid = JournalLine.objects.active().filter(
            account=self.payable_account
        ).aggregate(v=Sum("debit"))["v"] or Decimal("0")
        cash_direct = InventoryMovement.objects.active().filter(
            contact=self, movement_type="purchase"
        ).aggregate(v=Sum("total_cost"))["v"] or Decimal("0")
        return bill_paid + cash_direct

    def total_direct_cash_paid(self):
        """Total cost of inventory purchased directly with cash from this contact."""
        from inventory.models import InventoryMovement
        from django.db.models import Sum
        result = InventoryMovement.objects.active().filter(
            contact=self, movement_type="purchase",
        ).aggregate(v=Sum("total_cost"))["v"]
        return result or Decimal("0")

    # ------------------------------------------------------------------
    # Customer-side helpers
    # ------------------------------------------------------------------

    def balance_receivable(self):
        if not self.receivable_account:
            return Decimal("0")
        from journal.models import JournalLine
        lines = JournalLine.objects.active().filter(account=self.receivable_account)
        return sum(l.debit for l in lines) - sum(l.credit for l in lines)


# Backward-compatibility alias used by older migrations and imports that
# haven't been updated yet.  Remove once all references are updated.
Vendor = Contact
