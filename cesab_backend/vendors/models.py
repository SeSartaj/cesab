from django.db import models
from django.utils.translation import gettext_lazy as _


class Vendor(models.Model):
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE,
        related_name="vendors", verbose_name=_("Project")
    )
    name = models.CharField(max_length=200, verbose_name=_("Name"))
    phone = models.CharField(max_length=50, blank=True, verbose_name=_("Phone"))
    payable_account = models.ForeignKey(
        "coa.Account", on_delete=models.PROTECT,
        related_name="vendor_payable_accounts", verbose_name=_("Payable Account")
    )
    advance_account = models.ForeignKey(
        "coa.Account", on_delete=models.PROTECT,
        related_name="vendor_advance_accounts", verbose_name=_("Advance Account")
    )
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))

    class Meta:
        verbose_name = _("Vendor")
        verbose_name_plural = _("Vendors")
        ordering = ["name"]

    def __str__(self):
        return self.name

    def balance_payable(self):
        from journal.models import JournalLine
        lines = JournalLine.objects.active().filter(account=self.payable_account)
        return sum(l.credit for l in lines) - sum(l.debit for l in lines)

    def advance_balance(self):
        from journal.models import JournalLine
        lines = JournalLine.objects.active().filter(account=self.advance_account)
        return sum(l.debit for l in lines) - sum(l.credit for l in lines)
