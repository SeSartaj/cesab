from django.db import models
from django.utils.translation import gettext_lazy as _
from decimal import Decimal


class Account(models.Model):
    ACCOUNT_TYPES = [
        ("asset", _("Asset")),
        ("liability", _("Liability")),
        ("equity", _("Equity")),
        ("income", _("Income")),
        ("expense", _("Expense")),
    ]

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE,
        related_name="accounts", verbose_name=_("Project")
    )
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="children", verbose_name=_("Parent Account")
    )
    name = models.CharField(max_length=200, verbose_name=_("Name"))
    code = models.CharField(max_length=20, verbose_name=_("Code"))
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES, verbose_name=_("Type"))
    is_system = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))

    class Meta:
        unique_together = ("project", "code")
        ordering = ["code"]
        verbose_name = _("Account")
        verbose_name_plural = _("Accounts")

    def __str__(self):
        return f"{self.code} - {self.name}"

    def balance(self):
        from journal.models import JournalLine
        lines = JournalLine.objects.active().filter(account=self)
        total_debit = sum(l.debit for l in lines)
        total_credit = sum(l.credit for l in lines)
        if self.account_type in ("asset", "expense"):
            return total_debit - total_credit
        else:
            return total_credit - total_debit
