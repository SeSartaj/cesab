from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, DetailView
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.db.models import Sum
from decimal import Decimal

from projects.models import Project
from projects.permissions import can_access_financial
from inventory.models import InventoryMovement
from journal.models import JournalEntry, JournalLine
from .models import Vendor
from .forms import VendorForm
from .services import create_vendor


class VendorListView(LoginRequiredMixin, ListView):
    template_name = "vendors/vendor_list.html"
    context_object_name = "vendors"

    def get_queryset(self):
        self.project = get_object_or_404(Project, pk=self.kwargs["project_pk"])
        return Vendor.objects.filter(project=self.project, is_active=True)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["project"] = self.project
        ctx["title"] = _("Vendors")
        ctx["can_add_financial"] = can_access_financial(self.request.user, self.project)
        return ctx


@login_required
def add_vendor(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if not can_access_financial(request.user, project):
        messages.error(request, _("You do not have permission."))
        return redirect("projects:dashboard", pk=project_pk)

    if request.method == "POST":
        form = VendorForm(request.POST)
        if form.is_valid():
            create_vendor(
                project=project,
                name=form.cleaned_data["name"],
                phone=form.cleaned_data.get("phone", ""),
            )
            messages.success(request, _("Vendor created."))
            return redirect(reverse("projects:vendors", kwargs={"project_pk": project_pk}))
    else:
        form = VendorForm()

    return render(request, "vendors/vendor_form.html", {
        "project": project,
        "form": form,
        "title": _("New Vendor"),
    })


class VendorDetailView(LoginRequiredMixin, DetailView):
    model = Vendor
    template_name = "vendors/vendor_detail.html"
    context_object_name = "vendor"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        vendor = self.object
        ctx["project"] = vendor.project
        ctx["can_add_financial"] = can_access_financial(self.request.user, vendor.project)

        # --- Payable account stats ---
        # Bills = ALL credits on the payable account that create a liability
        # (vendor_bill, inventory_purchase on credit, or any future payable-
        #  creating type).  We explicitly exclude vendor_refund credits here
        # because those are tracked as a separate breakdown row (total_refunded).
        total_billed = JournalLine.objects.active().filter(
            account=vendor.payable_account,
        ).exclude(
            journal_entry__transaction_type="vendor_refund",
        ).aggregate(v=Sum("credit"))["v"] or Decimal("0")

        # Paid = debits on payable (payments + advance settlements)
        total_paid = JournalLine.objects.active().filter(
            account=vendor.payable_account,
        ).aggregate(v=Sum("debit"))["v"] or Decimal("0")

        # Refunds = credits on payable from vendor_refund entries
        total_refunded = JournalLine.objects.active().filter(
            account=vendor.payable_account,
            journal_entry__transaction_type="vendor_refund",
        ).aggregate(v=Sum("credit"))["v"] or Decimal("0")

        net_payable = total_billed - total_paid - total_refunded

        # --- Per-currency payable breakdown ---
        # Net owed in each transaction currency (credit_tc - debit_tc per currency)
        currency_rows = (
            JournalLine.objects.active()
            .filter(account=vendor.payable_account)
            .values("transaction_currency__code", "transaction_currency__symbol")
            .annotate(
                total_credit_tc=Sum("credit_tc"),
                total_debit_tc=Sum("debit_tc"),
            )
            .order_by("transaction_currency__code")
        )
        payable_by_currency = []
        for row in currency_rows:
            net_tc = (row["total_credit_tc"] or Decimal("0")) - (row["total_debit_tc"] or Decimal("0"))
            if abs(net_tc) >= Decimal("0.01"):
                payable_by_currency.append({
                    "code": row["transaction_currency__code"],
                    "symbol": row["transaction_currency__symbol"] or "",
                    "net_tc": net_tc,
                    "billed_tc": row["total_credit_tc"] or Decimal("0"),
                    "paid_tc": row["total_debit_tc"] or Decimal("0"),
                })

        # --- Direct cash purchases (vendor_cash payment method) ---
        cash_movements = InventoryMovement.objects.active().filter(
            vendor=vendor, movement_type="purchase",
        ).select_related("journal_entry")
        total_cash_direct = cash_movements.aggregate(
            v=Sum("total_cost")
        )["v"] or Decimal("0")
        cash_je_ids = list(cash_movements.values_list("journal_entry_id", flat=True).distinct())

        # Grand total ever paid to this vendor (bill payments + direct cash purchases)
        total_ever_paid = total_paid + total_cash_direct

        # --- Advance account stats ---
        adv_agg = JournalLine.objects.active().filter(account=vendor.advance_account).aggregate(
            total_debit=Sum("debit"),
            total_credit=Sum("credit"),
        )
        total_advances = adv_agg["total_debit"]  or Decimal("0")  # advances = DR
        total_settled  = adv_agg["total_credit"] or Decimal("0")  # settlements = CR
        net_advance    = total_advances - total_settled

        # Net amount actually owed (payable minus advances that offset it)
        net_due = net_payable - net_advance

        # --- Recent transactions: payable/advance account JEs + direct cash purchase JEs ---
        payable_je_ids = JournalLine.objects.active().filter(
            account_id__in=[vendor.payable_account_id, vendor.advance_account_id]
        ).values_list("journal_entry_id", flat=True).distinct()

        all_je_ids = set(payable_je_ids) | set(cash_je_ids)

        vendor_entries = JournalEntry.objects.filter(
            project=vendor.project,
            id__in=all_je_ids,
        ).prefetch_related("lines__transaction_currency").order_by("-date", "-id")[:20]

        # Enrich each JE with per-currency TC amounts from payable/advance lines.
        # Grouping by currency avoids meaningless cross-currency sums (e.g. USD + AFN).
        vendor_account_ids = {vendor.payable_account_id, vendor.advance_account_id}
        enriched_entries = []
        for je in vendor_entries:
            rel_lines = [l for l in je.lines.all() if l.account_id in vendor_account_ids]
            by_currency = {}
            for line in rel_lines:
                code = line.transaction_currency.code
                if code not in by_currency:
                    by_currency[code] = {"charged": Decimal("0"), "paid": Decimal("0")}
                by_currency[code]["charged"] += line.credit_tc  # credit on payable = you owe more
                by_currency[code]["paid"]    += line.debit_tc   # debit on payable  = you paid
            # Build sorted list, suppressing zero amounts
            amounts = [
                {"currency": code, "charged": v["charged"], "paid": v["paid"]}
                for code, v in sorted(by_currency.items())
                if v["charged"] or v["paid"]
            ]
            enriched_entries.append({
                "je": je,
                "amounts": amounts,
            })

        ctx.update({
            "total_billed":         total_billed,
            "total_paid":           total_paid,
            "total_refunded":       total_refunded,
            "net_payable":          net_payable,
            "total_advances":       total_advances,
            "total_settled":        total_settled,
            "net_advance":          net_advance,
            "net_due":              net_due,
            "total_cash_direct":    total_cash_direct,
            "total_ever_paid":      total_ever_paid,
            "vendor_entries":       enriched_entries,
            "payable_by_currency":  payable_by_currency,
        })
        return ctx

