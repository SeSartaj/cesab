from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class CashConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "cash"
    verbose_name = _("Cash")
