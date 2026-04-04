from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.views.generic import ListView, DetailView
from django.db.models import Q
import json

from projects.models import Project
from projects.permissions import can_access_financial
from core.models import Currency
from vendors.models import Contact
from .models import (
    Tax, VendorBill, CustomerInvoice, Payment, Receipt,
    VendorBillAttachment, CustomerInvoiceAttachment, _ALLOWED_EXTENSIONS,
)
from .forms import (
    TaxForm, VendorBillForm, CustomerInvoiceForm,
    PaymentForm, ReceiptForm, ReverseDocumentForm,
    make_bill_line_formset, make_invoice_line_formset,
)
import documents.services as svc


def _project(pk):
    return get_object_or_404(Project, pk=pk)


def _require_financial(request, project):
    if not can_access_financial(request.user, project):
        messages.error(request, _("You do not have permission."))
        return redirect("projects:dashboard", pk=project.pk)
    return None


# ---------------------------------------------------------------------------
# Taxes
# ---------------------------------------------------------------------------

@login_required
def tax_list(request, project_pk):
    project = _project(project_pk)
    taxes = Tax.objects.filter(project=project)
    return render(request, "documents/tax_list.html", {
        "project": project,
        "taxes": taxes,
        "title": _("Taxes"),
        "can_add_financial": can_access_financial(request.user, project),
        "can_edit_financial": can_access_financial(request.user, project),
    })


@login_required
def tax_create(request, project_pk):
    project = _project(project_pk)
    denied = _require_financial(request, project)
    if denied:
        return denied

    if request.method == "POST":
        form = TaxForm(project, request.POST)
        if form.is_valid():
            tax = form.save(commit=False)
            tax.project = project
            tax.save()
            messages.success(request, _("Tax created."))
            return redirect(reverse("projects:tax_list", kwargs={"project_pk": project_pk}))
    else:
        form = TaxForm(project)

    return render(request, "documents/tax_form.html", {
        "project": project, "form": form, "title": _("New Tax"),
    })


@login_required
def tax_edit(request, project_pk, pk):
    project = _project(project_pk)
    denied = _require_financial(request, project)
    if denied:
        return denied
    tax = get_object_or_404(Tax, pk=pk, project=project)

    if request.method == "POST":
        form = TaxForm(project, request.POST, instance=tax)
        if form.is_valid():
            form.save()
            messages.success(request, _("Tax updated."))
            return redirect(reverse("projects:tax_list", kwargs={"project_pk": project_pk}))
    else:
        form = TaxForm(project, instance=tax)

    return render(request, "documents/tax_form.html", {
        "project": project, "form": form, "title": _("Edit Tax"), "tax": tax,
    })


# ---------------------------------------------------------------------------
# Vendor Bills
# ---------------------------------------------------------------------------

class VendorBillListView(LoginRequiredMixin, ListView):
    model = VendorBill
    template_name = "documents/bill_list.html"
    context_object_name = "bills"

    def get_queryset(self):
        self.project = _project(self.kwargs["project_pk"])
        qs = VendorBill.objects.filter(project=self.project).select_related(
            "contact", "currency", "journal_entry"
        )
        q = self.request.GET.get("q", "").strip()
        currency_id = self.request.GET.get("currency", "").strip()
        contact_id = self.request.GET.get("contact", "").strip()
        if q:
            qs = qs.filter(
                Q(number__icontains=q) | Q(contact__name__icontains=q)
            )
        if currency_id:
            qs = qs.filter(currency_id=currency_id)
        if contact_id:
            qs = qs.filter(contact_id=contact_id)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["project"] = self.project
        ctx["title"] = _("Vendor Bills")
        ctx["can_add_financial"] = can_access_financial(self.request.user, self.project)
        ctx["today"] = timezone.now().date()
        # sorting by computed TC properties
        sort = self.request.GET.get("sort", "")
        bills = list(ctx["bills"])
        if sort == "paid_tc":
            bills.sort(key=lambda b: b.paid_tc())
        elif sort == "-paid_tc":
            bills.sort(key=lambda b: b.paid_tc(), reverse=True)
        elif sort == "balance_tc":
            bills.sort(key=lambda b: b.balance_tc())
        elif sort == "-balance_tc":
            bills.sort(key=lambda b: b.balance_tc(), reverse=True)
        ctx["bills"] = bills
        # filter options scoped to this project
        bill_ids = self.project.vendor_bills.values_list("pk", flat=True)
        ctx["filter_currencies"] = Currency.objects.filter(
            vendorbill__in=bill_ids
        ).distinct().order_by("code")
        ctx["filter_contacts"] = Contact.objects.filter(
            vendor_bills__in=bill_ids
        ).distinct().order_by("name")
        ctx["q"] = self.request.GET.get("q", "")
        ctx["selected_currency"] = self.request.GET.get("currency", "")
        ctx["selected_contact"] = self.request.GET.get("contact", "")
        ctx["current_sort"] = sort
        return ctx


@login_required
def bill_create(request, project_pk):
    project = _project(project_pk)
    denied = _require_financial(request, project)
    if denied:
        return denied

    LineFormSet = make_bill_line_formset(project, extra=1)

    if request.method == "POST":
        form = VendorBillForm(project, request.POST)
        formset = LineFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            bill = form.save(commit=False)
            bill.project = project
            bill.created_by = request.user
            bill.save()
            formset.instance = bill
            formset.save()
            messages.success(request, _("Bill saved as draft."))
            return redirect(reverse("projects:bill_detail", kwargs={"project_pk": project_pk, "pk": bill.pk}))
    else:
        form = VendorBillForm(project, initial={"date": timezone.now().date()})
        formset = LineFormSet()

    return render(request, "documents/bill_form.html", {
        "project": project, "form": form, "formset": formset,
        "title": _("New Vendor Bill"),
    })


@login_required
def bill_detail(request, project_pk, pk):
    project = _project(project_pk)
    bill = get_object_or_404(VendorBill, pk=pk, project=project)
    paid = bill.paid_bc()
    balance = bill.balance_bc()
    payments = bill.payments.filter(status="posted").select_related(
        "cashbox", "currency"
    ).order_by("date")
    attachments = bill.attachments.select_related("uploaded_by").order_by("uploaded_at")
    return render(request, "documents/bill_detail.html", {
        "project": project,
        "bill": bill,
        "title": bill.number,
        "can_add_financial": can_access_financial(request.user, project),
        "paid_bc": paid,
        "paid_tc": bill.paid_tc(),
        "balance_bc": balance,
        "balance_tc": bill.balance_tc(),
        "today": timezone.now().date(),
        "payments": payments,
        "attachments": attachments,
    })


@login_required
def bill_edit(request, project_pk, pk):
    project = _project(project_pk)
    denied = _require_financial(request, project)
    if denied:
        return denied
    bill = get_object_or_404(VendorBill, pk=pk, project=project)
    if bill.is_posted:
        messages.error(request, _("A posted bill cannot be edited. Reverse it first."))
        return redirect(reverse("projects:bill_detail", kwargs={"project_pk": project_pk, "pk": pk}))

    LineFormSet = make_bill_line_formset(project, extra=0)

    if request.method == "POST":
        form = VendorBillForm(project, request.POST, instance=bill)
        formset = LineFormSet(request.POST, instance=bill)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, _("Bill updated."))
            return redirect(reverse("projects:bill_detail", kwargs={"project_pk": project_pk, "pk": pk}))
    else:
        form = VendorBillForm(project, instance=bill)
        formset = LineFormSet(instance=bill)

    return render(request, "documents/bill_form.html", {
        "project": project, "form": form, "formset": formset,
        "title": _("Edit Bill"), "bill": bill,
    })


@login_required
def bill_post(request, project_pk, pk):
    project = _project(project_pk)
    denied = _require_financial(request, project)
    if denied:
        return denied
    bill = get_object_or_404(VendorBill, pk=pk, project=project)

    if request.method == "POST":
        try:
            svc.post_vendor_bill(bill, request.user)
            messages.success(request, _("Bill posted. Journal entry created."))
        except ValueError as e:
            messages.error(request, str(e))

    return redirect(reverse("projects:bill_detail", kwargs={"project_pk": project_pk, "pk": pk}))


@login_required
def bill_reverse(request, project_pk, pk):
    project = _project(project_pk)
    denied = _require_financial(request, project)
    if denied:
        return denied
    bill = get_object_or_404(VendorBill, pk=pk, project=project)

    if request.method == "POST":
        form = ReverseDocumentForm(request.POST)
        if form.is_valid():
            try:
                reversal = svc.reverse_vendor_bill(
                    bill, request.user,
                    date=form.cleaned_data["date"],
                    notes=form.cleaned_data.get("notes", ""),
                )
                messages.success(request, _("Bill reversed. Reversal: %(num)s") % {"num": reversal.number})
                return redirect(reverse("projects:bill_detail", kwargs={"project_pk": project_pk, "pk": reversal.pk}))
            except ValueError as e:
                messages.error(request, str(e))
    else:
        form = ReverseDocumentForm(initial={"date": timezone.now().date()})

    return render(request, "documents/reverse_form.html", {
        "project": project, "form": form,
        "document": bill, "title": _("Reverse Bill"),
    })


# ---------------------------------------------------------------------------
# Customer Invoices
# ---------------------------------------------------------------------------

class CustomerInvoiceListView(LoginRequiredMixin, ListView):
    model = CustomerInvoice
    template_name = "documents/invoice_list.html"
    context_object_name = "invoices"

    def get_queryset(self):
        self.project = _project(self.kwargs["project_pk"])
        return CustomerInvoice.objects.filter(project=self.project).select_related(
            "contact", "currency", "journal_entry"
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["project"] = self.project
        ctx["title"] = _("Customer Invoices")
        ctx["can_add_financial"] = can_access_financial(self.request.user, self.project)
        ctx["today"] = timezone.now().date()
        return ctx


@login_required
def invoice_create(request, project_pk):
    project = _project(project_pk)
    denied = _require_financial(request, project)
    if denied:
        return denied

    LineFormSet = make_invoice_line_formset(project, extra=1)

    if request.method == "POST":
        form = CustomerInvoiceForm(project, request.POST)
        formset = LineFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            invoice = form.save(commit=False)
            invoice.project = project
            invoice.created_by = request.user
            invoice.save()
            formset.instance = invoice
            formset.save()
            messages.success(request, _("Invoice saved as draft."))
            return redirect(reverse("projects:invoice_detail", kwargs={"project_pk": project_pk, "pk": invoice.pk}))
    else:
        form = CustomerInvoiceForm(project, initial={"date": timezone.now().date()})
        formset = LineFormSet()

    return render(request, "documents/invoice_form.html", {
        "project": project, "form": form, "formset": formset,
        "title": _("New Customer Invoice"),
    })


@login_required
def invoice_detail(request, project_pk, pk):
    project = _project(project_pk)
    invoice = get_object_or_404(CustomerInvoice, pk=pk, project=project)
    received = invoice.received_bc()
    balance = invoice.balance_bc()
    receipts = invoice.receipts.filter(status="posted").select_related(
        "cashbox", "currency"
    ).order_by("date")
    attachments = invoice.attachments.select_related("uploaded_by").order_by("uploaded_at")
    return render(request, "documents/invoice_detail.html", {
        "project": project,
        "invoice": invoice,
        "title": invoice.number,
        "can_add_financial": can_access_financial(request.user, project),
        "received_bc": received,
        "received_tc": invoice.received_tc(),
        "balance_bc": balance,
        "balance_tc": invoice.balance_tc(),
        "today": timezone.now().date(),
        "receipts": receipts,
        "attachments": attachments,
    })


@login_required
def invoice_edit(request, project_pk, pk):
    project = _project(project_pk)
    denied = _require_financial(request, project)
    if denied:
        return denied
    invoice = get_object_or_404(CustomerInvoice, pk=pk, project=project)
    if invoice.is_posted:
        messages.error(request, _("A posted invoice cannot be edited. Reverse it first."))
        return redirect(reverse("projects:invoice_detail", kwargs={"project_pk": project_pk, "pk": pk}))

    LineFormSet = make_invoice_line_formset(project, extra=0)

    if request.method == "POST":
        form = CustomerInvoiceForm(project, request.POST, instance=invoice)
        formset = LineFormSet(request.POST, instance=invoice)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, _("Invoice updated."))
            return redirect(reverse("projects:invoice_detail", kwargs={"project_pk": project_pk, "pk": pk}))
    else:
        form = CustomerInvoiceForm(project, instance=invoice)
        formset = LineFormSet(instance=invoice)

    return render(request, "documents/invoice_form.html", {
        "project": project, "form": form, "formset": formset,
        "title": _("Edit Invoice"), "invoice": invoice,
    })


@login_required
def invoice_post(request, project_pk, pk):
    project = _project(project_pk)
    denied = _require_financial(request, project)
    if denied:
        return denied
    invoice = get_object_or_404(CustomerInvoice, pk=pk, project=project)

    if request.method == "POST":
        try:
            svc.post_customer_invoice(invoice, request.user)
            messages.success(request, _("Invoice posted. Journal entry created."))
        except ValueError as e:
            messages.error(request, str(e))

    return redirect(reverse("projects:invoice_detail", kwargs={"project_pk": project_pk, "pk": pk}))


@login_required
def invoice_reverse(request, project_pk, pk):
    project = _project(project_pk)
    denied = _require_financial(request, project)
    if denied:
        return denied
    invoice = get_object_or_404(CustomerInvoice, pk=pk, project=project)

    if request.method == "POST":
        form = ReverseDocumentForm(request.POST)
        if form.is_valid():
            try:
                reversal = svc.reverse_customer_invoice(
                    invoice, request.user,
                    date=form.cleaned_data["date"],
                    notes=form.cleaned_data.get("notes", ""),
                )
                messages.success(request, _("Invoice reversed."))
                return redirect(reverse("projects:invoice_detail", kwargs={"project_pk": project_pk, "pk": reversal.pk}))
            except ValueError as e:
                messages.error(request, str(e))
    else:
        form = ReverseDocumentForm(initial={"date": timezone.now().date()})

    return render(request, "documents/reverse_form.html", {
        "project": project, "form": form,
        "document": invoice, "title": _("Reverse Invoice"),
    })


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------

class PaymentListView(LoginRequiredMixin, ListView):
    model = Payment
    template_name = "documents/payment_list.html"
    context_object_name = "payments"

    def get_queryset(self):
        self.project = _project(self.kwargs["project_pk"])
        return Payment.objects.filter(
            project=self.project,
            reversal_of__isnull=True,
            reversed_by__isnull=True,
        ).select_related("contact", "currency", "cashbox")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["project"] = self.project
        ctx["title"] = _("Payments")
        ctx["can_add_financial"] = can_access_financial(self.request.user, self.project)
        return ctx


def _bill_balance_info(project, form):
    """Return balance dict for the bill currently selected in *form*, or None."""
    try:
        bill_pk = form["bill"].value()
    except Exception:
        return None
    if not bill_pk:
        return None
    try:
        b = VendorBill.objects.get(pk=bill_pk, project=project)
    except VendorBill.DoesNotExist:
        return None
    return {
        "number": b.number,
        "total_tc": b.total_amount(),
        "currency_code": b.currency.code,
        "currency_id": b.currency_id,
        "exchange_rate": b.exchange_rate,   # BC per 1 bill-TC unit
        "paid_tc": b.paid_tc(),
        "balance_tc": b.balance_tc(),
    }


def _build_bills_json(project):
    """Return JSON-serialisable dict of all posted bills for this project."""
    data = {}
    for b in VendorBill.objects.filter(project=project, status="posted").select_related("currency", "contact"):
        data[str(b.pk)] = {
            "number": b.number,
            "contact_id": b.contact_id,
            "currency_id": b.currency_id,
            "currency_code": b.currency.code,
            "currency_symbol": b.currency.symbol or "",
            "booking_rate": float(b.exchange_rate),
            "total_tc": float(b.total_amount()),
            "paid_tc": float(b.paid_tc()),
            "balance_tc": float(b.balance_tc()),
        }
    return json.dumps(data)


def _build_invoices_json(project):
    """Return JSON-serialisable dict of all posted customer invoices."""
    data = {}
    for inv in CustomerInvoice.objects.filter(project=project, status="posted").select_related("currency", "contact"):
        data[str(inv.pk)] = {
            "number": inv.number,
            "contact_id": inv.contact_id,
            "currency_id": inv.currency_id,
            "currency_code": inv.currency.code,
            "currency_symbol": inv.currency.symbol or "",
            "booking_rate": float(inv.exchange_rate),
            "total_tc": float(inv.total_amount()),
            "received_tc": float(inv.received_tc()),
            "balance_tc": float(inv.balance_tc()),
        }
    return json.dumps(data)


def _build_cashboxes_json(project):
    """Return JSON-serialisable dict of active cashboxes for the project."""
    from cash.models import Cashbox
    data = {}
    for cb in Cashbox.objects.filter(project=project, is_active=True).select_related("currency"):
        data[str(cb.pk)] = {
            "name": cb.name,
            "currency_id": cb.currency_id,
            "currency_code": cb.currency.code,
            "currency_symbol": cb.currency.symbol or "",
        }
    return json.dumps(data)


def _invoice_balance_info(project, form):
    """Return balance dict for the invoice currently selected in *form*, or None."""
    try:
        inv_pk = form["invoice"].value()
    except Exception:
        return None
    if not inv_pk:
        return None
    try:
        inv = CustomerInvoice.objects.get(pk=inv_pk, project=project)
    except CustomerInvoice.DoesNotExist:
        return None
    return {
        "number": inv.number,
        "total_tc": inv.total_amount(),
        "currency_code": inv.currency.code,
        "currency_id": inv.currency_id,
        "exchange_rate": inv.exchange_rate,   # BC per 1 invoice-TC unit
        "received_tc": inv.received_tc(),
        "balance_tc": inv.balance_tc(),
    }


@login_required
def payment_create(request, project_pk):
    project = _project(project_pk)
    denied = _require_financial(request, project)
    if denied:
        return denied

    if request.method == "POST":
        form = PaymentForm(project, request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.project = project
            payment.created_by = request.user
            payment.save()
            messages.success(request, _("Payment saved as draft."))
            return redirect(reverse("projects:payment_detail", kwargs={"project_pk": project_pk, "pk": payment.pk}))
    else:
        initial = {"date": timezone.now().date()}
        bill_pk = request.GET.get("bill")
        if bill_pk:
            try:
                bill_obj = VendorBill.objects.get(pk=bill_pk, project=project, status="posted")
                initial["bill"] = bill_obj
                initial["contact"] = bill_obj.contact
                initial["currency"] = bill_obj.currency
            except VendorBill.DoesNotExist:
                pass
        form = PaymentForm(project, initial=initial)

    bill_info = _bill_balance_info(project, form)
    return render(request, "documents/payment_form.html", {
        "project": project, "form": form, "title": _("New Payment"),
        "bill_info": bill_info,
        "bills_json": _build_bills_json(project),
        "cashboxes_json": _build_cashboxes_json(project),
        "base_currency_id": project.base_currency_id,
        "base_currency_code": project.base_currency.code,
        "base_currency_symbol": project.base_currency.symbol or "",
    })


@login_required
def payment_edit(request, project_pk, pk):
    project = _project(project_pk)
    denied = _require_financial(request, project)
    if denied:
        return denied
    payment = get_object_or_404(Payment, pk=pk, project=project)
    if payment.is_posted:
        messages.error(request, _("A posted payment cannot be edited. Reverse it first."))
        return redirect(reverse("projects:payment_detail", kwargs={"project_pk": project_pk, "pk": pk}))

    if request.method == "POST":
        form = PaymentForm(project, request.POST, instance=payment)
        if form.is_valid():
            form.save()
            messages.success(request, _("Payment updated."))
            return redirect(reverse("projects:payment_detail", kwargs={"project_pk": project_pk, "pk": pk}))
    else:
        form = PaymentForm(project, instance=payment)

    bill_info = _bill_balance_info(project, form)
    return render(request, "documents/payment_form.html", {
        "project": project, "form": form, "title": _("Edit Payment"), "payment": payment,
        "bill_info": bill_info,
        "bills_json": _build_bills_json(project),
        "cashboxes_json": _build_cashboxes_json(project),
        "base_currency_id": project.base_currency_id,
        "base_currency_code": project.base_currency.code,
        "base_currency_symbol": project.base_currency.symbol or "",
    })


@login_required
def payment_detail(request, project_pk, pk):
    project = _project(project_pk)
    payment = get_object_or_404(Payment, pk=pk, project=project)
    return render(request, "documents/payment_detail.html", {
        "project": project, "payment": payment, "title": payment.number,
        "can_add_financial": can_access_financial(request.user, project),
        "can_edit_financial": can_access_financial(request.user, project),
    })


@login_required
def payment_post(request, project_pk, pk):
    project = _project(project_pk)
    denied = _require_financial(request, project)
    if denied:
        return denied
    payment = get_object_or_404(Payment, pk=pk, project=project)

    if request.method == "POST":
        try:
            svc.post_payment(payment, request.user)
            messages.success(request, _("Payment posted."))
        except ValueError as e:
            messages.error(request, str(e))

    return redirect(reverse("projects:payment_detail", kwargs={"project_pk": project_pk, "pk": pk}))


@login_required
def payment_reverse(request, project_pk, pk):
    project = _project(project_pk)
    denied = _require_financial(request, project)
    if denied:
        return denied
    payment = get_object_or_404(Payment, pk=pk, project=project)

    if request.method == "POST":
        form = ReverseDocumentForm(request.POST)
        if form.is_valid():
            try:
                reversal = svc.reverse_payment(
                    payment, request.user,
                    date=form.cleaned_data["date"],
                    notes=form.cleaned_data.get("notes", ""),
                )
                messages.success(request, _("Payment reversed."))
                return redirect(reverse("projects:payment_detail", kwargs={"project_pk": project_pk, "pk": reversal.pk}))
            except ValueError as e:
                messages.error(request, str(e))
    else:
        form = ReverseDocumentForm(initial={"date": timezone.now().date()})

    return render(request, "documents/reverse_form.html", {
        "project": project, "form": form,
        "document": payment, "title": _("Reverse Payment"),
    })


# ---------------------------------------------------------------------------
# Receipts
# ---------------------------------------------------------------------------

class ReceiptListView(LoginRequiredMixin, ListView):
    model = Receipt
    template_name = "documents/receipt_list.html"
    context_object_name = "receipts"

    def get_queryset(self):
        self.project = _project(self.kwargs["project_pk"])
        return Receipt.objects.filter(
            project=self.project,
            reversal_of__isnull=True,
            reversed_by__isnull=True,
        ).select_related("contact", "currency", "cashbox")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["project"] = self.project
        ctx["title"] = _("Receipts")
        ctx["can_add_financial"] = can_access_financial(self.request.user, self.project)
        return ctx


@login_required
def receipt_create(request, project_pk):
    project = _project(project_pk)
    denied = _require_financial(request, project)
    if denied:
        return denied

    if request.method == "POST":
        form = ReceiptForm(project, request.POST)
        if form.is_valid():
            receipt = form.save(commit=False)
            receipt.project = project
            receipt.created_by = request.user
            receipt.save()
            messages.success(request, _("Receipt saved as draft."))
            return redirect(reverse("projects:receipt_detail", kwargs={"project_pk": project_pk, "pk": receipt.pk}))
    else:
        initial = {"date": timezone.now().date()}
        invoice_pk = request.GET.get("invoice")
        if invoice_pk:
            try:
                inv_obj = CustomerInvoice.objects.get(pk=invoice_pk, project=project, status="posted")
                initial["invoice"] = inv_obj
                initial["contact"] = inv_obj.contact
            except CustomerInvoice.DoesNotExist:
                pass
        form = ReceiptForm(project, initial=initial)

    invoice_info = _invoice_balance_info(project, form)
    return render(request, "documents/receipt_form.html", {
        "project": project, "form": form, "title": _("New Receipt"),
        "invoice_info": invoice_info,
        "invoices_json": _build_invoices_json(project),
        "cashboxes_json": _build_cashboxes_json(project),
        "base_currency_id": project.base_currency_id,
        "base_currency_code": project.base_currency.code,
        "base_currency_symbol": project.base_currency.symbol or "",
    })


@login_required
def receipt_edit(request, project_pk, pk):
    project = _project(project_pk)
    denied = _require_financial(request, project)
    if denied:
        return denied
    receipt = get_object_or_404(Receipt, pk=pk, project=project)
    if receipt.is_posted:
        messages.error(request, _("A posted receipt cannot be edited. Reverse it first."))
        return redirect(reverse("projects:receipt_detail", kwargs={"project_pk": project_pk, "pk": pk}))

    if request.method == "POST":
        form = ReceiptForm(project, request.POST, instance=receipt)
        if form.is_valid():
            form.save()
            messages.success(request, _("Receipt updated."))
            return redirect(reverse("projects:receipt_detail", kwargs={"project_pk": project_pk, "pk": pk}))
    else:
        form = ReceiptForm(project, instance=receipt)

    invoice_info = _invoice_balance_info(project, form)
    return render(request, "documents/receipt_form.html", {
        "project": project, "form": form, "title": _("Edit Receipt"), "receipt": receipt,
        "invoice_info": invoice_info,
        "invoices_json": _build_invoices_json(project),
        "cashboxes_json": _build_cashboxes_json(project),
        "base_currency_id": project.base_currency_id,
        "base_currency_code": project.base_currency.code,
        "base_currency_symbol": project.base_currency.symbol or "",
    })


@login_required
def receipt_detail(request, project_pk, pk):
    project = _project(project_pk)
    receipt = get_object_or_404(Receipt, pk=pk, project=project)
    return render(request, "documents/receipt_detail.html", {
        "project": project, "receipt": receipt, "title": receipt.number,
        "can_add_financial": can_access_financial(request.user, project),
        "can_edit_financial": can_access_financial(request.user, project),
    })


@login_required
def receipt_post(request, project_pk, pk):
    project = _project(project_pk)
    denied = _require_financial(request, project)
    if denied:
        return denied
    receipt = get_object_or_404(Receipt, pk=pk, project=project)

    if request.method == "POST":
        try:
            svc.post_receipt(receipt, request.user)
            messages.success(request, _("Receipt posted."))
        except ValueError as e:
            messages.error(request, str(e))

    return redirect(reverse("projects:receipt_detail", kwargs={"project_pk": project_pk, "pk": pk}))


@login_required
def receipt_reverse(request, project_pk, pk):
    project = _project(project_pk)
    denied = _require_financial(request, project)
    if denied:
        return denied
    receipt = get_object_or_404(Receipt, pk=pk, project=project)

    if request.method == "POST":
        form = ReverseDocumentForm(request.POST)
        if form.is_valid():
            try:
                reversal = svc.reverse_receipt(
                    receipt, request.user,
                    date=form.cleaned_data["date"],
                    notes=form.cleaned_data.get("notes", ""),
                )
                messages.success(request, _("Receipt reversed."))
                return redirect(reverse("projects:receipt_detail", kwargs={"project_pk": project_pk, "pk": reversal.pk}))
            except ValueError as e:
                messages.error(request, str(e))
    else:
        form = ReverseDocumentForm(initial={"date": timezone.now().date()})

    return render(request, "documents/reverse_form.html", {
        "project": project, "form": form,
        "document": receipt, "title": _("Reverse Receipt"),
    })


# ── Attachment views ─────────────────────────────────────────────────────────

import os as _os


def _validate_attachment(f):
    """Return error message if file extension not allowed, else None."""
    ext = _os.path.splitext(f.name)[1].lower()
    if ext not in _ALLOWED_EXTENSIONS:
        return _("Only PDF, JPG, PNG, GIF, and WEBP files are allowed.")
    return None


@login_required
def bill_attachment_upload(request, project_pk, pk):
    project = _project(project_pk)
    denied = _require_financial(request, project)
    if denied:
        return denied
    bill = get_object_or_404(VendorBill, pk=pk, project=project)
    if request.method == "POST":
        f = request.FILES.get("file")
        if not f:
            messages.error(request, _("No file selected."))
        else:
            err = _validate_attachment(f)
            if err:
                messages.error(request, err)
            else:
                VendorBillAttachment.objects.create(
                    bill=bill,
                    file=f,
                    original_name=f.name,
                    uploaded_by=request.user,
                )
                messages.success(request, _("File attached."))
    return redirect(reverse("projects:bill_detail", kwargs={"project_pk": project_pk, "pk": pk}))


@login_required
def bill_attachment_delete(request, project_pk, pk, att_pk):
    project = _project(project_pk)
    denied = _require_financial(request, project)
    if denied:
        return denied
    att = get_object_or_404(VendorBillAttachment, pk=att_pk, bill__pk=pk, bill__project=project)
    if request.method == "POST":
        att.file.delete(save=False)
        att.delete()
        messages.success(request, _("Attachment removed."))
    return redirect(reverse("projects:bill_detail", kwargs={"project_pk": project_pk, "pk": pk}))


@login_required
def invoice_attachment_upload(request, project_pk, pk):
    project = _project(project_pk)
    denied = _require_financial(request, project)
    if denied:
        return denied
    invoice = get_object_or_404(CustomerInvoice, pk=pk, project=project)
    if request.method == "POST":
        f = request.FILES.get("file")
        if not f:
            messages.error(request, _("No file selected."))
        else:
            err = _validate_attachment(f)
            if err:
                messages.error(request, err)
            else:
                CustomerInvoiceAttachment.objects.create(
                    invoice=invoice,
                    file=f,
                    original_name=f.name,
                    uploaded_by=request.user,
                )
                messages.success(request, _("File attached."))
    return redirect(reverse("projects:invoice_detail", kwargs={"project_pk": project_pk, "pk": pk}))


@login_required
def invoice_attachment_delete(request, project_pk, pk, att_pk):
    project = _project(project_pk)
    denied = _require_financial(request, project)
    if denied:
        return denied
    att = get_object_or_404(CustomerInvoiceAttachment, pk=att_pk, invoice__pk=pk, invoice__project=project)
    if request.method == "POST":
        att.file.delete(save=False)
        att.delete()
        messages.success(request, _("Attachment removed."))
    return redirect(reverse("projects:invoice_detail", kwargs={"project_pk": project_pk, "pk": pk}))
