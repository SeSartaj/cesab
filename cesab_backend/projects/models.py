from django.db import models
from django.conf import settings
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


class ProjectMember(models.Model):
    """Links a staff/accountant user to a project with an explicit role."""
    ROLE_CHOICES = [
        ("admin", _("Admin")),
        ("accountant", _("Accountant")),
        ("viewer", _("Viewer")),
    ]
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE,
        related_name="members", verbose_name=_("Project")
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="project_memberships", verbose_name=_("User")
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="viewer", verbose_name=_("Role"))

    class Meta:
        unique_together = ("project", "user")
        verbose_name = _("Project Member")
        verbose_name_plural = _("Project Members")

    def __str__(self):
        return f"{self.user} → {self.project} ({self.role})"
