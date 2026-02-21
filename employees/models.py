from django.db import models
from django.utils.translation import gettext_lazy as _


class ProjectEmployee(models.Model):
    SALARY_TYPES = [
        ("monthly", _("Monthly")),
        ("daily", _("Daily")),
    ]

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE,
        related_name="employees", verbose_name=_("Project")
    )
    name = models.CharField(max_length=200, verbose_name=_("Name"))
    salary_type = models.CharField(max_length=20, choices=SALARY_TYPES, verbose_name=_("Salary Type"))
    salary_amount = models.DecimalField(max_digits=18, decimal_places=2, verbose_name=_("Salary Amount"))
    expense_account = models.ForeignKey(
        "coa.Account", on_delete=models.PROTECT,
        related_name="employee_expense_accounts", verbose_name=_("Expense Account")
    )
    payable_account = models.ForeignKey(
        "coa.Account", on_delete=models.PROTECT,
        related_name="employee_payable_accounts", verbose_name=_("Payable Account")
    )
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))

    class Meta:
        verbose_name = _("Employee")
        verbose_name_plural = _("Employees")
        ordering = ["name"]

    def __str__(self):
        return self.name
