from django.db import models
from django.utils.translation import gettext_lazy as _


class Cashbox(models.Model):
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE,
        related_name="cashboxes", verbose_name=_("Project")
    )
    name = models.CharField(max_length=200, verbose_name=_("Name"))
    account = models.OneToOneField(
        "coa.Account", on_delete=models.CASCADE, verbose_name=_("Account")
    )
    currency = models.ForeignKey(
        "core.Currency", on_delete=models.PROTECT, verbose_name=_("Currency")
    )
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))

    class Meta:
        verbose_name = _("Cashbox")
        verbose_name_plural = _("Cashboxes")

    def __str__(self):
        return self.name

    def balance(self):
        from journal.models import JournalLine
        lines = JournalLine.objects.filter(account=self.account)
        return sum(l.debit for l in lines) - sum(l.credit for l in lines)

    def balance_in_currency(self):
        """Balance expressed in the cashbox's own currency (transaction currency)."""
        from journal.models import JournalLine
        lines = JournalLine.objects.filter(account=self.account)
        return sum(l.debit_tc for l in lines) - sum(l.credit_tc for l in lines)
