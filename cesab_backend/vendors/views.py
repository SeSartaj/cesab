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
from projects.permissions import require_accounting
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
        return ctx


@login_required
def add_vendor(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    denied = require_accounting(request, project)
    if denied:
        return denied

    if request.method == "POST":
        form = VendorForm(request.POST)
        if form.is_valid():
            create_vendor(
                project=project,
                user=request.user,
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

        # --- Payable account stats ---
        # Bills = credits on payable from vendor_bill entries
        total_billed = JournalLine.objects.active().filter(
            account=vendor.payable_account,
            journal_entry__transaction_type="vendor_bill",
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

        # --- Recent transactions touching either vendor account ---
        je_ids = JournalLine.objects.active().filter(
            account_id__in=[vendor.payable_account_id, vendor.advance_account_id]
        ).values_list("journal_entry_id", flat=True).distinct()

        vendor_entries = JournalEntry.objects.filter(
            project=vendor.project,
            id__in=je_ids,
        ).prefetch_related("lines").order_by("-date", "-id")[:20]

        ctx.update({
            "total_billed":    total_billed,
            "total_paid":      total_paid,
            "total_refunded":  total_refunded,
            "net_payable":     net_payable,
            "total_advances":  total_advances,
            "total_settled":   total_settled,
            "net_advance":     net_advance,
            "net_due":         net_due,
            "vendor_entries":  vendor_entries,
        })
        return ctx

