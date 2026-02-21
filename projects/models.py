from django.db import models
from django.utils.translation import gettext_lazy as _


class Project(models.Model):
    name = models.CharField(max_length=200, verbose_name=_("Project Name"))
    description = models.TextField(blank=True, verbose_name=_("Description"))
    base_currency = models.ForeignKey(
        "core.Currency", on_delete=models.PROTECT, verbose_name=_("Base Currency")
    )
    start_date = models.DateField(null=True, blank=True, verbose_name=_("Start Date"))
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))

    class Meta:
        verbose_name = _("Project")
        verbose_name_plural = _("Projects")
        ordering = ["-created_at"]

    def __str__(self):
        return self.name
