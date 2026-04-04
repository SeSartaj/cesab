from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.db.models import Sum
from decimal import Decimal

from projects.models import Project
from projects.views import _project_permission_ctx, _require_project_access
from .models import Account
from .forms import AccountForm

# Maps account_type → leading digit of the code range
_TYPE_PREFIX = {
    "asset": "1",
    "liability": "2",
    "equity": "3",
    "income": "4",
    "expense": "5",
}


def _suggest_code(project, account_type):
    """Return the next available 4-digit code for *account_type* in *project*."""
    prefix = _TYPE_PREFIX.get(account_type)
    if not prefix:
        return ""
    existing = [
        int(c) for c in
        Account.objects.filter(project=project, account_type=account_type)
        .values_list("code", flat=True)
        if c.isdigit() and c.startswith(prefix)
    ]
    if not existing:
        return f"{prefix}100"
    max_code = max(existing)
    # Round up to the next multiple of 10
    suggested = ((max_code // 10) + 1) * 10
    return str(suggested)


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
        perm_ctx = _project_permission_ctx(self.request.user, self.project)
        ctx.update(perm_ctx)
        return ctx


@login_required
def account_create(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if not _require_project_access(request.user, project, "projects.add_financial_data"):
        messages.error(request, _("You do not have permission to add accounts."))
        return redirect("projects:coa", project_pk=project_pk)

    type_hint = request.GET.get("type") or ""
    valid_types = {t for t, _ in Account.ACCOUNT_TYPES}
    if type_hint not in valid_types:
        type_hint = ""

    if request.method == "POST":
        form = AccountForm(project, request.POST, account_type=request.POST.get("account_type") or None)
        if form.is_valid():
            account = form.save(commit=False)
            account.project = project
            account.save()
            messages.success(request, _("Account created."))
            return redirect("projects:coa", project_pk=project_pk)
    else:
        initial = {}
        if type_hint:
            initial["account_type"] = type_hint
            initial["code"] = _suggest_code(project, type_hint)
        form = AccountForm(project, initial=initial, account_type=type_hint or None)

    return render(request, "coa/account_form.html", {
        "project": project,
        "form": form,
        "title": _("New Account"),
        "locked_type": type_hint,
    })


@login_required
def account_edit(request, project_pk, pk):
    project = get_object_or_404(Project, pk=project_pk)
    if not _require_project_access(request.user, project, "projects.add_financial_data"):
        messages.error(request, _("You do not have permission to edit accounts."))
        return redirect("projects:coa", project_pk=project_pk)

    account = get_object_or_404(Account, pk=pk, project=project)

    if request.method == "POST":
        form = AccountForm(project, request.POST, instance=account)
        if form.is_valid():
            form.save()
            messages.success(request, _("Account updated."))
            return redirect("projects:coa", project_pk=project_pk)
    else:
        form = AccountForm(project, instance=account)

    return render(request, "coa/account_form.html", {
        "project": project,
        "form": form,
        "account": account,
        "title": _("Edit Account"),
    })


@login_required
def trial_balance(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)

    date_from = request.GET.get("date_from", "")
    date_to   = request.GET.get("date_to", "")

    from journal.models import JournalLine

    line_qs = JournalLine.objects.active().filter(account__project=project)
    if date_from:
        line_qs = line_qs.filter(journal_entry__date__gte=date_from)
    if date_to:
        line_qs = line_qs.filter(journal_entry__date__lte=date_to)

    # Two aggregations: one pass each for debit and credit totals per account
    debit_map  = {
        r["account_id"]: r["total"]
        for r in line_qs.values("account_id").annotate(total=Sum("debit"))
    }
    credit_map = {
        r["account_id"]: r["total"]
        for r in line_qs.values("account_id").annotate(total=Sum("credit"))
    }

    accounts = Account.objects.filter(project=project, is_active=True).order_by("code")
    rows = []
    grand_debit  = Decimal("0")
    grand_credit = Decimal("0")

    for acc in accounts:
        d = debit_map.get(acc.pk, Decimal("0")) or Decimal("0")
        c = credit_map.get(acc.pk, Decimal("0")) or Decimal("0")
        if d == 0 and c == 0:
            continue
        rows.append({
            "account":       acc,
            "total_debit":   d,
            "total_credit":  c,
            "net_debit":     max(d - c, Decimal("0")),
            "net_credit":    max(c - d, Decimal("0")),
        })
        grand_debit  += d
        grand_credit += c

    is_balanced = grand_debit == grand_credit

    # Group rows by account type for display
    from collections import OrderedDict
    groups = OrderedDict()
    for type_code, type_label in ACCOUNT_TYPES:
        type_rows = [r for r in rows if r["account"].account_type == type_code]
        if type_rows:
            groups[type_label] = type_rows

    return render(request, "coa/trial_balance.html", {
        "project":      project,
        "groups":       groups,
        "grand_debit":  grand_debit,
        "grand_credit": grand_credit,
        "is_balanced":  is_balanced,
        "date_from":    date_from,
        "date_to":      date_to,
    })
