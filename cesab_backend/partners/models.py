from django.db import models
from django.utils.translation import gettext_lazy as _


class ProjectPartner(models.Model):
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE,
        related_name="project_partners", verbose_name=_("Project")
    )
    name = models.CharField(max_length=200, verbose_name=_("Name"))
    user = models.ForeignKey(
        "auth_users.User", on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="project_participations", verbose_name=_("User")
    )
    ownership_percent = models.DecimalField(max_digits=5, decimal_places=2, verbose_name=_("Ownership %"))
    capital_commitment = models.DecimalField(max_digits=18, decimal_places=2, verbose_name=_("Capital Commitment"))
    capital_account = models.ForeignKey(
        "coa.Account", on_delete=models.PROTECT,
        related_name="partner_capital_accounts", verbose_name=_("Capital Account")
    )
    current_account = models.ForeignKey(
        "coa.Account", on_delete=models.PROTECT,
        related_name="partner_current_accounts", verbose_name=_("Current Account")
    )
    joined_at = models.DateField(verbose_name=_("Joined At"))
    exited_at = models.DateField(null=True, blank=True, verbose_name=_("Exited At"))
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))

    class Meta:
        verbose_name = _("Project Partner")
        verbose_name_plural = _("Project Partners")

    def __str__(self):
        return f"{self.name} - {self.project.name}"

    def contributed_amount(self):
        from journal.models import JournalLine
        lines = JournalLine.objects.active().filter(account=self.capital_account)
        return sum(l.credit for l in lines)

    def remaining_commitment(self):
        return self.capital_commitment - self.contributed_amount()
