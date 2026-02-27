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
        permissions = [
            # Custom object-level permissions used with django-guardian.
            # ROLE_PERMISSIONS in projects/permissions.py maps each role to
            # the subset it receives.
            ("manage_members", "Can manage project members"),
            ("add_financial_data", "Can add / edit financial data"),
        ]

    def __str__(self):
        return self.name


class ProjectMember(models.Model):
    """Links a user to a project with an explicit role.

    Saving or deleting a ProjectMember automatically synchronises the user's
    django-guardian object-level permissions for that project so the rest of
    the codebase can simply call ``user.has_perm("projects.view_project", project)``.
    """

    ROLE_ADMIN = "admin"
    ROLE_ACCOUNTANT = "accountant"
    ROLE_VIEWER = "viewer"

    ROLE_CHOICES = [
        (ROLE_ADMIN, _("Admin")),
        (ROLE_ACCOUNTANT, _("Accountant")),
        (ROLE_VIEWER, _("Viewer")),
    ]

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE,
        related_name="members", verbose_name=_("Project")
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="project_memberships", verbose_name=_("User")
    )
    role = models.CharField(
        max_length=20, choices=ROLE_CHOICES,
        default=ROLE_VIEWER, verbose_name=_("Role")
    )

    class Meta:
        unique_together = ("project", "user")
        verbose_name = _("Project Member")
        verbose_name_plural = _("Project Members")

    def __str__(self):
        return f"{self.user} → {self.project} ({self.role})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Sync guardian object permissions whenever a member is created or
        # their role changes.  Import is deferred to avoid circular imports.
        from .permissions import assign_role_permissions
        assign_role_permissions(self.user, self.project, self.role)

    def delete(self, *args, **kwargs):
        user, project = self.user, self.project
        super().delete(*args, **kwargs)
        from .permissions import revoke_all_permissions
        revoke_all_permissions(user, project)
