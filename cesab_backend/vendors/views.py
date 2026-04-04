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
from .models import Contact
from .forms import ContactForm
from .services import create_contact


class ContactListView(LoginRequiredMixin, ListView):
    template_name = "vendors/contact_list.html"
    context_object_name = "contacts"

    def get_queryset(self):
        self.project = get_object_or_404(Project, pk=self.kwargs["project_pk"])
        q = self.request.GET.get("q", "").strip()
        type_filter = self.request.GET.get("type")
        qs = Contact.objects.filter(project=self.project, is_active=True)
        if type_filter in (Contact.VENDOR, Contact.CUSTOMER, Contact.BOTH):
            qs = qs.filter(contact_type=type_filter)
        if q:
            qs = qs.filter(name__icontains=q)
        return qs.order_by("name")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["project"] = self.project
        ctx["title"] = _("Contacts")
        ctx["can_add_financial"] = can_access_financial(self.request.user, self.project)
        ctx["type_filter"] = self.request.GET.get("type", "")
        ctx["q"] = self.request.GET.get("q", "")
        sort = self.request.GET.get("sort", "")
        ctx["sort"] = sort
        contacts = list(ctx["contacts"])
        if sort == "payable":
            contacts.sort(key=lambda c: c.balance_payable(), reverse=True)
        elif sort == "-payable":
            contacts.sort(key=lambda c: c.balance_payable())
        elif sort == "receivable":
            contacts.sort(key=lambda c: c.balance_receivable(), reverse=True)
        elif sort == "-receivable":
            contacts.sort(key=lambda c: c.balance_receivable())
        ctx["contacts"] = contacts
        ctx["vendors"] = contacts
        return ctx


@login_required
def add_contact(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if not can_access_financial(request.user, project):
        messages.error(request, _("You do not have permission."))
        return redirect("projects:dashboard", pk=project_pk)

    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            create_contact(
                project=project,
                name=form.cleaned_data["name"],
                phone=form.cleaned_data.get("phone", ""),
                contact_type=form.cleaned_data.get("contact_type", Contact.VENDOR),
            )
            messages.success(request, _("Contact created."))
            return redirect(reverse("projects:contacts", kwargs={"project_pk": project_pk}))
    else:
        form = ContactForm()

    return render(request, "vendors/vendor_form.html", {
        "project": project,
        "form": form,
        "title": _("New Contact"),
    })


class ContactDetailView(LoginRequiredMixin, DetailView):
    model = Contact
    template_name = "vendors/vendor_detail.html"
    context_object_name = "contact"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        contact = self.object
        ctx["project"] = contact.project
        ctx["can_add_financial"] = can_access_financial(self.request.user, contact.project)
        # keep template compat
        ctx["vendor"] = contact

        if contact.is_vendor and contact.payable_account:
            total_billed = JournalLine.objects.active().filter(
                account=contact.payable_account,
            ).exclude(
                journal_entry__transaction_type="vendor_refund",
            ).aggregate(v=Sum("credit"))["v"] or Decimal("0")

            total_paid = JournalLine.objects.active().filter(
                account=contact.payable_account,
            ).aggregate(v=Sum("debit"))["v"] or Decimal("0")

            total_refunded = JournalLine.objects.active().filter(
                account=contact.payable_account,
                journal_entry__transaction_type="vendor_refund",
            ).aggregate(v=Sum("credit"))["v"] or Decimal("0")

            net_payable = total_billed - total_paid - total_refunded

            currency_rows = (
                JournalLine.objects.active()
                .filter(account=contact.payable_account)
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

            cash_movements = InventoryMovement.objects.active().filter(
                contact=contact, movement_type="purchase",
            ).select_related("journal_entry")
            total_cash_direct = cash_movements.aggregate(v=Sum("total_cost"))["v"] or Decimal("0")
            cash_je_ids = list(cash_movements.values_list("journal_entry_id", flat=True).distinct())

            total_ever_paid = total_paid + total_cash_direct

            adv_agg = JournalLine.objects.active().filter(
                account=contact.advance_account
            ).aggregate(
                total_debit=Sum("debit"),
                total_credit=Sum("credit"),
            ) if contact.advance_account else {"total_debit": None, "total_credit": None}
            total_advances = adv_agg["total_debit"] or Decimal("0")
            total_settled = adv_agg["total_credit"] or Decimal("0")
            net_advance = total_advances - total_settled
            net_due = net_payable - net_advance

            account_ids = {
                a for a in [contact.payable_account_id, contact.advance_account_id] if a
            }
            payable_je_ids = JournalLine.objects.active().filter(
                account_id__in=account_ids
            ).values_list("journal_entry_id", flat=True).distinct()

            all_je_ids = set(payable_je_ids) | set(cash_je_ids)
            vendor_entries = JournalEntry.objects.filter(
                project=contact.project, id__in=all_je_ids,
            ).prefetch_related("lines__transaction_currency").order_by("-date", "-id")[:20]

            enriched_entries = []
            for je in vendor_entries:
                rel_lines = [l for l in je.lines.all() if l.account_id in account_ids]
                by_currency = {}
                for line in rel_lines:
                    code = line.transaction_currency.code
                    if code not in by_currency:
                        by_currency[code] = {"charged": Decimal("0"), "paid": Decimal("0")}
                    by_currency[code]["charged"] += line.credit_tc
                    by_currency[code]["paid"] += line.debit_tc
                amounts = [
                    {"currency": code, "charged": v["charged"], "paid": v["paid"]}
                    for code, v in sorted(by_currency.items())
                    if v["charged"] or v["paid"]
                ]
                enriched_entries.append({"je": je, "amounts": amounts})

            ctx.update({
                "total_billed": total_billed,
                "total_paid": total_paid,
                "total_refunded": total_refunded,
                "net_payable": net_payable,
                "total_advances": total_advances,
                "total_settled": total_settled,
                "net_advance": net_advance,
                "net_due": net_due,
                "total_cash_direct": total_cash_direct,
                "total_ever_paid": total_ever_paid,
                "vendor_entries": enriched_entries,
                "payable_by_currency": payable_by_currency,
            })

        if contact.is_customer and contact.receivable_account:
            rec_agg = JournalLine.objects.active().filter(
                account=contact.receivable_account
            ).aggregate(total_debit=Sum("debit"), total_credit=Sum("credit"))
            total_invoiced = rec_agg["total_debit"] or Decimal("0")
            total_received = rec_agg["total_credit"] or Decimal("0")
            ctx.update({
                "total_invoiced": total_invoiced,
                "total_received": total_received,
                "net_receivable": total_invoiced - total_received,
            })

        return ctx

