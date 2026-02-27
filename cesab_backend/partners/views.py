import json
from decimal import Decimal

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from projects.models import Project
from projects.permissions import can_access_financial
from .models import ProjectPartner
from .forms import AddPartnerToProjectForm
from .services import add_partner_to_project


class ShareholderListView(LoginRequiredMixin, ListView):
    template_name = "partners/shareholder_list.html"
    context_object_name = "project_partners"

    def get_queryset(self):
        self.project = get_object_or_404(Project, pk=self.kwargs["project_pk"])
        # Fetch ALL partners (active + exited), active ones first, then alphabetical
        return (
            ProjectPartner.objects.filter(project=self.project)
            .select_related("user", "capital_account")
            .order_by("-is_active", "name")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        all_partners = list(self.object_list)

        # ── Per-partner stats (pass 1) ────────────────────────────────────
        rows = []
        active_fulfillments = []

        for pp in all_partners:
            contributed = pp.contributed_amount()  # base-currency Decimal
            commitment = pp.capital_commitment

            if commitment > 0:
                fulfillment_pct = float(contributed / commitment * 100)
            else:
                fulfillment_pct = 0.0

            # Only active partners with a real commitment set the benchmark
            if pp.is_active and commitment > 0:
                active_fulfillments.append(fulfillment_pct)

            rows.append({
                "partner": pp,
                "contributed": contributed,
                "fulfillment_pct": round(fulfillment_pct, 1),
                "expected": Decimal("0"),
                "shortfall": Decimal("0"),
            })

        # ── Benchmark: highest commitment-fulfillment % among active partners
        benchmark_pct = max(active_fulfillments) if active_fulfillments else 0.0

        # ── Per-partner stats (pass 2): expected & shortfall ──────────────
        for row in rows:
            pp = row["partner"]
            if pp.capital_commitment > 0:
                expected = (
                    Decimal(str(round(benchmark_pct / 100, 10)))
                    * pp.capital_commitment
                )
            else:
                expected = Decimal("0")
            shortfall = max(Decimal("0"), expected - row["contributed"])
            row["expected"] = expected
            row["shortfall"] = shortfall

        # ── Aggregate totals (active partners only) ───────────────────────
        active_rows = [r for r in rows if r["partner"].is_active]
        total_committed = sum(r["partner"].capital_commitment for r in active_rows)
        total_contributed = sum(r["contributed"] for r in active_rows)
        total_expected = sum(r["expected"] for r in active_rows)
        total_shortfall = sum(r["shortfall"] for r in active_rows)

        # ── Chart data (all partners, JSON arrays) ────────────────────────
        labels = [r["partner"].name for r in rows]
        chart_committed = [float(r["partner"].capital_commitment) for r in rows]
        chart_contributed = [float(r["contributed"]) for r in rows]
        chart_expected = [float(r["expected"]) for r in rows]
        chart_ownership = [float(r["partner"].ownership_percent) for r in rows]

        grand_total_contributed = sum(r["contributed"] for r in rows)
        if grand_total_contributed > 0:
            chart_contribution_shares = [
                round(float(r["contributed"] / grand_total_contributed * 100), 2)
                for r in rows
            ]
        else:
            chart_contribution_shares = [0.0] * len(rows)

        # ── Contribution timeline (last 50 entries across all partners) ───
        from journal.models import JournalLine

        account_ids = [pp.capital_account_id for pp in all_partners]
        account_to_partner = {pp.capital_account_id: pp.name for pp in all_partners}

        timeline_lines = (
            JournalLine.objects.active()
            .filter(
                account_id__in=account_ids,
                credit__gt=0,
                journal_entry__transaction_type__in=[
                    "capital_contribution",
                    "partner_inventory_contribution",
                ],
            )
            .select_related("journal_entry", "transaction_currency")
            .order_by("-journal_entry__date", "-journal_entry__id")
        )[:50]

        timeline = [
            {
                "date": line.journal_entry.date,
                "partner_name": account_to_partner.get(line.account_id, "—"),
                "amount_base": line.credit,
                "amount_tc": line.credit_tc,
                "currency_code": line.transaction_currency.code,
                "exchange_rate": line.exchange_rate,
                "tx_type": line.journal_entry.transaction_type,
                "description": line.journal_entry.description,
            }
            for line in timeline_lines
        ]

        ctx.update({
            "project": self.project,
            "title": _("Shareholders"),
            "can_add_financial": can_access_financial(self.request.user, self.project),
            "partner_rows": rows,
            "benchmark_pct": round(benchmark_pct, 1),
            "total_committed": total_committed,
            "total_contributed": total_contributed,
            "total_expected": total_expected,
            "total_shortfall": total_shortfall,
            "timeline": timeline,
            "chart_labels": json.dumps(labels),
            "chart_committed": json.dumps(chart_committed),
            "chart_contributed": json.dumps(chart_contributed),
            "chart_expected": json.dumps(chart_expected),
            "chart_ownership": json.dumps(chart_ownership),
            "chart_contribution_shares": json.dumps(chart_contribution_shares),
        })
        return ctx


@login_required
def add_shareholder(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if not can_access_financial(request.user, project):
        messages.error(request, _("You do not have permission to perform this action."))
        return redirect("projects:dashboard", pk=project_pk)

    if request.method == "POST":
        form = AddPartnerToProjectForm(request.POST)
        if form.is_valid():
            add_partner_to_project(
                project=project,
                name=form.cleaned_data["name"],
                user=form.cleaned_data.get("user"),
                ownership_percent=form.cleaned_data["ownership_percent"],
                capital_commitment=form.cleaned_data["capital_commitment"],
                joined_at=form.cleaned_data["joined_at"],
            )
            messages.success(request, _("Partner added to project."))
            return redirect(reverse("projects:dashboard", kwargs={"pk": project_pk}) + "#shareholders")
    else:
        form = AddPartnerToProjectForm(initial={"joined_at": timezone.now().date()})

    return render(request, "partners/add_shareholder.html", {
        "project": project,
        "form": form,
        "title": _("Add Shareholder"),
    })
