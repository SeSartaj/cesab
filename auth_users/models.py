from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    ROLE_CHOICES = [
        ("admin", _("Admin")),
        ("accountant", _("Accountant")),
        ("viewer", _("Viewer")),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="viewer", verbose_name=_("Role"))
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")

    def __str__(self):
        return self.username

    @property
    def can_edit(self):
        return self.role in ("admin", "accountant")

    @property
    def is_admin_role(self):
        return self.role == "admin"
