from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _

from projects.models import Project
from .models import Account


ACCOUNT_TYPES = [
    ("asset", _("Assets")),
    ("liability", _("Liabilities")),
    ("equity", _("Equity")),
    ("income", _("Income")),
    ("expense", _("Expenses")),
]


class AccountListView(LoginRequiredMixin, ListView):
    template_name = "coa/account_list.html"
    context_object_name = "accounts"

    def get_queryset(self):
        self.project = get_object_or_404(Project, pk=self.kwargs["project_pk"])
        return Account.objects.filter(project=self.project, is_active=True).order_by("code")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["project"] = self.project
        ctx["title"] = _("Chart of Accounts")
        ctx["account_types"] = ACCOUNT_TYPES
        return ctx
