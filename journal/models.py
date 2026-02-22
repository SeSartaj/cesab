from django.db import models
from django.utils.translation import gettext_lazy as _
from decimal import Decimal


TRANSACTION_TYPES = [
    ("capital_contribution", _("Capital Contribution")),
    ("shareholder_withdrawal", _("Shareholder Withdrawal")),
    ("vendor_bill", _("Vendor Bill")),
    ("vendor_advance", _("Vendor Advance Payment")),
    ("vendor_payment", _("Vendor Payment Against Bill")),
    ("vendor_advance_settlement", _("Vendor Advance Settlement")),
    ("vendor_direct_payment", _("Vendor Direct Payment")),
    ("vendor_refund", _("Vendor Refund")),
    ("cash_expense", _("Cash Expense")),
    ("cashbox_transfer", _("Cashbox Transfer")),
    ("bank_deposit", _("Bank Deposit / Cash Withdrawal")),
    ("project_income", _("Project Income")),
    ("asset_purchase", _("Asset Purchase")),
    ("pay_salary", _("Pay Salary")),
    ("inventory_purchase", _("Inventory Purchase")),
    ("inventory_consumption", _("Inventory Consumption")),
    ("inventory_adjustment", _("Inventory Adjustment")),
    ("partner_inventory_contribution", _("Partner Inventory Contribution")),
    ("correction", _("Correction Entry")),
    ("manual", _("Manual Journal Entry")),
]


class JournalEntry(models.Model):
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE,
        related_name="journal_entries", verbose_name=_("Project")
    )
    date = models.DateField(verbose_name=_("Date"))
    description = models.TextField(blank=True, verbose_name=_("Description"))
    transaction_type = models.CharField(
        max_length=50, choices=TRANSACTION_TYPES, default="manual",
        verbose_name=_("Transaction Type")
    )
    reference = models.CharField(max_length=100, blank=True, verbose_name=_("Reference"))
    corrects = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="corrections", verbose_name=_("Corrects Entry"),
        help_text=_("If this is a correction entry, reference the original entry here."),
    )
    created_by = models.ForeignKey(
        "auth_users.User", on_delete=models.PROTECT, verbose_name=_("Created By")
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Journal Entry")
        verbose_name_plural = _("Journal Entries")
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"JE-{self.id:04d}"

    def total_debit(self):
        return sum(l.debit for l in self.lines.all())

    def total_credit(self):
        return sum(l.credit for l in self.lines.all())

    def is_balanced(self):
        return self.total_debit() == self.total_credit()


class JournalLine(models.Model):
    journal_entry = models.ForeignKey(
        "journal.JournalEntry", on_delete=models.CASCADE,
        related_name="lines", verbose_name=_("Journal Entry")
    )
    account = models.ForeignKey(
        "coa.Account", on_delete=models.PROTECT, verbose_name=_("Account")
    )
    debit = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"), verbose_name=_("Debit"))
    credit = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"), verbose_name=_("Credit"))
    transaction_currency = models.ForeignKey(
        "core.Currency", on_delete=models.PROTECT, verbose_name=_("Currency")
    )
    exchange_rate = models.DecimalField(max_digits=18, decimal_places=6, default=Decimal("1"), verbose_name=_("Exchange Rate"))
    debit_tc = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"), verbose_name=_("Debit (TC)"))
    credit_tc = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"), verbose_name=_("Credit (TC)"))
    description = models.CharField(max_length=300, blank=True, verbose_name=_("Description"))

    class Meta:
        verbose_name = _("Journal Line")
        verbose_name_plural = _("Journal Lines")

    def __str__(self):
        return f"{self.account} Dr:{self.debit} Cr:{self.credit}"
