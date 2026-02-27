from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.generic import DetailView
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.db.models import Sum
from django.core.paginator import Paginator
from decimal import Decimal
import urllib.parse

from projects.models import Project
from projects.permissions import can_access_financial
from coa.models import Account
from core.models import Currency
from .models import JournalEntry, JournalLine, TRANSACTION_TYPES
import transactions.services as tx_svc


@login_required
def journal_list(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)

    # --- Filter params ---
    tx_type    = request.GET.get("tx_type", "")
    date_from  = request.GET.get("date_from", "")
    date_to    = request.GET.get("date_to", "")
    currency_id = request.GET.get("currency", "")
    account_id  = request.GET.get("account", "")
    search_desc = request.GET.get("q", "").strip()

    # --- Build JE queryset (used in both modes) ---
    qs = JournalEntry.objects.filter(project=project).select_related("created_by")
    if tx_type:
        qs = qs.filter(transaction_type=tx_type)
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    if currency_id:
        qs = qs.filter(lines__transaction_currency_id=currency_id).distinct()
    if account_id:
        qs = qs.filter(lines__account_id=account_id).distinct()
    if search_desc:
        qs = qs.filter(description__icontains=search_desc)

    # --- Ledger mode (account selected) ---
    ledger_lines       = None
    selected_account   = None
    ledger_total_debit = Decimal("0")
    ledger_total_credit = Decimal("0")
    ledger_balance     = Decimal("0")

    if account_id:
        try:
            selected_account = Account.objects.get(pk=int(account_id), project=project)
        except (Account.DoesNotExist, ValueError):
            pass

        if selected_account:
            line_qs = JournalLine.objects.filter(
                account=selected_account,
                journal_entry__project=project,
            )
            if date_from:
                line_qs = line_qs.filter(journal_entry__date__gte=date_from)
            if date_to:
                line_qs = line_qs.filter(journal_entry__date__lte=date_to)
            if tx_type:
                line_qs = line_qs.filter(journal_entry__transaction_type=tx_type)
            if currency_id:
                line_qs = line_qs.filter(transaction_currency_id=currency_id)
            if search_desc:
                line_qs = line_qs.filter(journal_entry__description__icontains=search_desc)

            line_qs = line_qs.select_related(
                "journal_entry", "journal_entry__created_by", "transaction_currency"
            ).order_by("journal_entry__date", "journal_entry__id", "id")

            running = Decimal("0")
            rows = []
            for line in line_qs:
                ledger_total_debit  += line.debit
                ledger_total_credit += line.credit
                # Running balance: debit-normal for asset/expense, credit-normal for others
                if selected_account.account_type in ("asset", "expense"):
                    running += line.debit - line.credit
                else:
                    running += line.credit - line.debit
                rows.append({"line": line, "running": running})
            ledger_lines   = rows
            ledger_balance = running

    # --- Normal mode: totals + pagination ---
    total_debit  = Decimal("0")
    total_credit = Decimal("0")
    page_obj     = None
    entries      = []
    is_paginated = False

    if not account_id:
        agg = JournalLine.objects.filter(journal_entry__in=qs).aggregate(
            td=Sum("debit"), tc=Sum("credit")
        )
        total_debit  = agg["td"] or Decimal("0")
        total_credit = agg["tc"] or Decimal("0")

        paginator = Paginator(qs.prefetch_related("lines").order_by("-date", "-id"), 30)
        page_obj  = paginator.get_page(request.GET.get("page", 1))
        entries   = page_obj.object_list
        is_paginated = paginator.num_pages > 1

    # --- Filter options ---
    currencies = Currency.objects.filter(is_active=True).order_by("code")
    accounts   = Account.objects.filter(project=project, is_active=True).order_by("code")

    # Build query strings that preserve filters (without 'page')
    fdict = {k: request.GET[k] for k in ("date_from", "date_to", "tx_type", "currency", "account", "q") if request.GET.get(k)}
    filter_qs = urllib.parse.urlencode(fdict)
    # Same but without 'account' — used by the "Clear account" link
    fdict_no_account = {k: v for k, v in fdict.items() if k != "account"}
    filter_qs_no_account = urllib.parse.urlencode(fdict_no_account)
    # Same but without 'q' — used by the "Clear search" button
    fdict_no_q = {k: v for k, v in fdict.items() if k != "q"}
    filter_qs_no_q = urllib.parse.urlencode(fdict_no_q)

    return render(request, "journal/je_list.html", {
        "project":            project,
        "entries":            entries,
        "page_obj":           page_obj,
        "is_paginated":       is_paginated,
        "tx_types":           TRANSACTION_TYPES,
        "currencies":         currencies,
        "accounts":           accounts,
        "selected_currency_id": currency_id,
        "selected_account_id":  account_id,
        "selected_account":   selected_account,
        "ledger_lines":       ledger_lines,
        "ledger_total_debit": ledger_total_debit,
        "ledger_total_credit": ledger_total_credit,
        "ledger_balance":     ledger_balance,
        "total_debit":        total_debit,
        "total_credit":       total_credit,
        "filter_qs":          filter_qs,
        "filter_qs_no_account": filter_qs_no_account,
        "filter_qs_no_q":     filter_qs_no_q,
        "search_desc":        search_desc,
        "title":              _("Journal / Ledger"),
    })


class JournalEntryDetailView(LoginRequiredMixin, DetailView):
    model = JournalEntry
    template_name = "journal/je_detail.html"
    context_object_name = "entry"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["project"] = self.object.project
        ctx["corrections"] = self.object.corrections.all()
        ctx["can_add_financial"] = can_access_financial(self.request.user, self.object.project)
        return ctx


@login_required
def create_correction(request, project_pk, je_pk):
    """Create a counter-balancing correction entry. Journal entries can never be deleted."""
    project = get_object_or_404(Project, pk=project_pk)
    original_je = get_object_or_404(JournalEntry, pk=je_pk, project=project)

    if not can_access_financial(request.user, project):
        messages.error(request, _("You do not have permission to perform this action."))
        return redirect(reverse("projects:je_detail", kwargs={"project_pk": project_pk, "pk": je_pk}))

    if request.method == "POST":
        description = request.POST.get("description", "").strip()
        correction_je = tx_svc.create_correction_entry(
            original_je=original_je,
            user=request.user,
            description=description,
        )
        messages.success(
            request,
            _("Correction entry JE-%(pk)04d created successfully.") % {"pk": correction_je.pk}
        )
        return redirect(reverse("projects:je_detail", kwargs={"project_pk": project_pk, "pk": correction_je.pk}))

    return render(request, "journal/create_correction.html", {
        "project": project,
        "original_je": original_je,
        "title": _("Create Correction Entry"),
    })
