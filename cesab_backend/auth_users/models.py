from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")

    def __str__(self):
        return self.username

    @property
    def can_edit(self):
        """True for superusers and members of the Accountant group."""
        return (
            self.is_superuser
            or self.groups.filter(name="Accountant").exists()
        )

    @property
    def is_admin_role(self):
        return self.is_superuser or self.has_perm("auth_users.change_user")
