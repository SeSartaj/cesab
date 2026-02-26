from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, DetailView
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from decimal import Decimal

from projects.models import Project
from projects.permissions import require_accounting
from .models import Cashbox
from .forms import CashboxForm
from .services import create_cashbox


class CashboxListView(LoginRequiredMixin, ListView):
    template_name = "cash/cashbox_list.html"
    context_object_name = "cashboxes"

    def get_queryset(self):
        self.project = get_object_or_404(Project, pk=self.kwargs["project_pk"])
        return Cashbox.objects.filter(project=self.project, is_active=True).select_related("account", "currency")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["project"] = self.project
        ctx["title"] = _("Cashboxes")
        ctx["cashbox_data"] = [
            (cb,
             cb.balance_in_currency() if cb.currency != self.project.base_currency else cb.balance(),
             cb.balance())
            for cb in ctx["cashboxes"]
        ]
        return ctx


@login_required
def add_cashbox(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    denied = require_accounting(request, project)
    if denied:
        return denied

    if request.method == "POST":
        form = CashboxForm(request.POST)
        if form.is_valid():
            create_cashbox(
                project=project,
                user=request.user,
                name=form.cleaned_data["name"],
                currency=form.cleaned_data["currency"],
            )
            messages.success(request, _("Cashbox created."))
            return redirect(reverse("projects:dashboard", kwargs={"pk": project_pk}))
    else:
        form = CashboxForm()

    return render(request, "cash/cashbox_form.html", {
        "project": project,
        "form": form,
        "title": _("New Cashbox"),
    })


class CashboxDetailView(LoginRequiredMixin, DetailView):
    model = Cashbox
    template_name = "cash/cashbox_detail.html"
    context_object_name = "cashbox"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        cb = self.object
        ctx["project"] = cb.project

        from journal.models import JournalLine
        lines = JournalLine.objects.active().filter(
            account=cb.account
        ).select_related(
            "journal_entry", "journal_entry__created_by", "transaction_currency"
        ).order_by("journal_entry__date", "journal_entry__id", "id")

        # For foreign-currency cashboxes show amounts in the cashbox's own currency
        # (debit_tc / credit_tc).  For base-currency cashboxes use BC amounts.
        is_foreign = cb.currency != cb.project.base_currency

        running   = Decimal("0")
        total_in  = Decimal("0")
        total_out = Decimal("0")
        cash_flows = []
        for line in lines:
            if is_foreign:
                inflow     = line.debit_tc
                outflow    = line.credit_tc
                inflow_bc  = line.debit
                outflow_bc = line.credit
            else:
                inflow     = line.debit
                outflow    = line.credit
                inflow_bc  = None
                outflow_bc = None

            total_in  += inflow
            total_out += outflow
            running   += inflow - outflow
            cash_flows.append({
                "je":          line.journal_entry,
                "date":        line.journal_entry.date,
                "description": line.journal_entry.description,
                "tx_type":     line.journal_entry.get_transaction_type_display(),
                "inflow":      inflow,
                "outflow":     outflow,
                "inflow_bc":   inflow_bc,
                "outflow_bc":  outflow_bc,
                "running":     running,
            })

        ctx["cash_flows"]       = cash_flows
        ctx["balance"]          = running
        ctx["total_in"]         = total_in
        ctx["total_out"]        = total_out
        ctx["is_foreign_cashbox"] = is_foreign
        return ctx
