from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from projects.models import Project
from projects.permissions import can_access_financial
from cash.models import Cashbox
from coa.models import Account
from journal.models import JournalEntry, JournalLine
from vendors.models import Vendor
import transactions.services as svc
from . import forms as tx_forms


def _require_edit(request, project):
    if not can_access_financial(request.user, project):
        messages.error(request, _("You do not have permission."))
        return redirect("projects:dashboard", pk=project.pk)
    return None


def _dash_redirect(project_pk):
    return redirect(reverse("projects:dashboard", kwargs={"pk": project_pk}))


@login_required
def capital_contribution(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    denied = _require_edit(request, project)
    if denied:
        return denied

    if request.method == "POST":
        form = tx_forms.CapitalContributionForm(project, request.POST)
        if form.is_valid():
            d = form.cleaned_data
            use_base = d.get("use_base_currency", True)
            currency = None if use_base else d.get("currency")
            exchange_rate = 1 if use_base else (d.get("exchange_rate") or 1)
            svc.capital_contribution(
                project=project, user=request.user,
                date=d["date"], project_partner=d["project_partner"],
                amount=d["amount"], cashbox=d["cashbox"],
                description=d.get("description", ""),
                currency=currency, exchange_rate=exchange_rate,
            )
            messages.success(request, _("Capital contribution recorded."))
            return _dash_redirect(project_pk)
    else:
        form = tx_forms.CapitalContributionForm(project, initial={"date": timezone.now().date(), "use_base_currency": True})

    return render(request, "transactions/tx_form.html", {
        "project": project, "form": form,
        "title": _("Capital Contribution"),
        "tx_type": "capital_contribution",
    })


@login_required
def shareholder_withdrawal(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    denied = _require_edit(request, project)
    if denied:
        return denied

    if request.method == "POST":
        form = tx_forms.ShareholderWithdrawalForm(project, request.POST)
        if form.is_valid():
            d = form.cleaned_data
            use_base = d.get("use_base_currency", True)
            currency = None if use_base else d.get("currency")
            exchange_rate = 1 if use_base else (d.get("exchange_rate") or 1)
            try:
                svc.shareholder_withdrawal(
                    project=project, user=request.user,
                    date=d["date"], project_partner=d["project_partner"],
                    amount=d["amount"], cashbox=d["cashbox"],
                    description=d.get("description", ""),
                    currency=currency, exchange_rate=exchange_rate,
                )
                messages.success(request, _("Withdrawal recorded."))
                return _dash_redirect(project_pk)
            except ValueError as e:
                messages.error(request, str(e))
    else:
        form = tx_forms.ShareholderWithdrawalForm(project, initial={"date": timezone.now().date(), "use_base_currency": True})

    return render(request, "transactions/tx_form.html", {
        "project": project, "form": form,
        "title": _("Shareholder Withdrawal"),
        "tx_type": "shareholder_withdrawal",
    })


@login_required
def vendor_bill(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    denied = _require_edit(request, project)
    if denied:
        return denied

    # Pre-select vendor if provided via query string (?vendor=<pk>)
    initial_vendor_pk = request.GET.get("vendor")
    initial = {"date": timezone.now().date(), "use_base_currency": True}
    if initial_vendor_pk:
        try:
            initial["vendor"] = Vendor.objects.get(pk=initial_vendor_pk, project=project)
        except Vendor.DoesNotExist:
            pass

    if request.method == "POST":
        form = tx_forms.VendorBillForm(project, request.POST)
        if form.is_valid():
            d = form.cleaned_data
            use_base = d.get("use_base_currency", True)
            currency = None if use_base else d.get("currency")
            exchange_rate = 1 if use_base else (d.get("exchange_rate") or 1)
            svc.vendor_bill(
                project=project, user=request.user,
                date=d["date"], vendor=d["vendor"],
                expense_account=d["expense_account"], amount=d["amount"],
                description=d.get("description", ""),
                currency=currency, exchange_rate=exchange_rate,
            )
            messages.success(request, _("Vendor bill recorded."))
            return _dash_redirect(project_pk)
    else:
        form = tx_forms.VendorBillForm(project, initial=initial)

    return render(request, "transactions/tx_form.html", {
        "project": project, "form": form,
        "title": _("Vendor Bill"),
        "tx_type": "vendor_bill",
    })


@login_required
def vendor_advance(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    denied = _require_edit(request, project)
    if denied:
        return denied

    if request.method == "POST":
        form = tx_forms.VendorAdvanceForm(project, request.POST)
        if form.is_valid():
            d = form.cleaned_data
            use_base = d.get("use_base_currency", True)
            currency = None if use_base else d.get("currency")
            exchange_rate = 1 if use_base else (d.get("exchange_rate") or 1)
            try:
                svc.vendor_advance_payment(
                    project=project, user=request.user,
                    date=d["date"], vendor=d["vendor"],
                    amount=d["amount"], cashbox=d["cashbox"],
                    description=d.get("description", ""),
                    currency=currency, exchange_rate=exchange_rate,
                )
                messages.success(request, _("Vendor advance payment recorded."))
                return _dash_redirect(project_pk)
            except ValueError as e:
                messages.error(request, str(e))
    else:
        form = tx_forms.VendorAdvanceForm(project, initial={"date": timezone.now().date(), "use_base_currency": True})

    return render(request, "transactions/tx_form.html", {
        "project": project, "form": form,
        "title": _("Vendor Advance Payment"),
        "tx_type": "vendor_advance",
    })


@login_required
def vendor_payment(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    denied = _require_edit(request, project)
    if denied:
        return denied

    if request.method == "POST":
        form = tx_forms.VendorPaymentForm(project, request.POST)
        if form.is_valid():
            d = form.cleaned_data
            use_base = d.get("use_base_currency", True)
            currency = None if use_base else d.get("currency")
            exchange_rate = 1 if use_base else (d.get("exchange_rate") or 1)
            try:
                svc.vendor_payment_against_bill(
                    project=project, user=request.user,
                    date=d["date"], vendor=d["vendor"],
                    amount=d["amount"], cashbox=d["cashbox"],
                    description=d.get("description", ""),
                    currency=currency, exchange_rate=exchange_rate,
                )
                messages.success(request, _("Vendor payment recorded."))
                return _dash_redirect(project_pk)
            except ValueError as e:
                messages.error(request, str(e))
    else:
        form = tx_forms.VendorPaymentForm(project, initial={"date": timezone.now().date(), "use_base_currency": True})

    return render(request, "transactions/tx_form.html", {
        "project": project, "form": form,
        "title": _("Vendor Payment Against Bill"),
        "tx_type": "vendor_payment",
    })


@login_required
def cash_expense(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    denied = _require_edit(request, project)
    if denied:
        return denied

    if request.method == "POST":
        form = tx_forms.CashExpenseForm(project, request.POST)
        if form.is_valid():
            d = form.cleaned_data
            try:
                svc.cash_expense(
                    project=project, user=request.user,
                    date=d["date"], expense_account=d["expense_account"],
                    amount=d["amount"], cashbox=d["cashbox"],
                    description=d.get("description", ""),
                    currency=d.get("currency"), exchange_rate=d.get("exchange_rate") or 1,
                )
                messages.success(request, _("Cash expense recorded."))
                return _dash_redirect(project_pk)
            except ValueError as e:
                messages.error(request, str(e))
    else:
        form = tx_forms.CashExpenseForm(project, initial={"date": timezone.now().date()})

    return render(request, "transactions/tx_form.html", {
        "project": project, "form": form,
        "title": _("Cash Expense"),
        "tx_type": "cash_expense",
    })


@login_required
def cashbox_transfer(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    denied = _require_edit(request, project)
    if denied:
        return denied

    if request.method == "POST":
        form = tx_forms.CashboxTransferForm(project, request.POST)
        if form.is_valid():
            d = form.cleaned_data
            try:
                svc.cashbox_transfer(
                    project=project, user=request.user,
                    date=d["date"], from_cashbox=d["from_cashbox"],
                    to_cashbox=d["to_cashbox"], amount=d["amount"],
                    description=d.get("description", ""),
                    currency=d.get("currency"), exchange_rate=d.get("exchange_rate") or 1,
                )
                messages.success(request, _("Cashbox transfer recorded."))
                return _dash_redirect(project_pk)
            except ValueError as e:
                messages.error(request, str(e))
    else:
        form = tx_forms.CashboxTransferForm(project, initial={"date": timezone.now().date()})

    return render(request, "transactions/tx_form.html", {
        "project": project, "form": form,
        "title": _("Cashbox Transfer"),
        "tx_type": "cashbox_transfer",
    })


@login_required
def bank_deposit(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    denied = _require_edit(request, project)
    if denied:
        return denied

    if request.method == "POST":
        form = tx_forms.BankDepositForm(project, request.POST)
        if form.is_valid():
            d = form.cleaned_data
            try:
                svc.bank_deposit(
                    project=project, user=request.user,
                    date=d["date"], from_cashbox=d["from_cashbox"],
                    to_cashbox=d["to_cashbox"], amount=d["amount"],
                    description=d.get("description", ""),
                    currency=d.get("currency"), exchange_rate=d.get("exchange_rate") or 1,
                )
                messages.success(request, _("Bank deposit / cash withdrawal recorded."))
                return _dash_redirect(project_pk)
            except ValueError as e:
                messages.error(request, str(e))
    else:
        form = tx_forms.BankDepositForm(project, initial={"date": timezone.now().date()})

    return render(request, "transactions/tx_form.html", {
        "project": project, "form": form,
        "title": _("Bank Deposit / Cash Withdrawal"),
        "tx_type": "bank_deposit",
    })


@login_required
def project_income(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    denied = _require_edit(request, project)
    if denied:
        return denied

    if request.method == "POST":
        form = tx_forms.ProjectIncomeForm(project, request.POST)
        if form.is_valid():
            d = form.cleaned_data
            svc.project_income(
                project=project, user=request.user,
                date=d["date"], cashbox=d["cashbox"],
                amount=d["amount"],
                description=d.get("description", ""),
                currency=d.get("currency"), exchange_rate=d.get("exchange_rate") or 1,
            )
            messages.success(request, _("Project income recorded."))
            return _dash_redirect(project_pk)
    else:
        form = tx_forms.ProjectIncomeForm(project, initial={"date": timezone.now().date()})

    return render(request, "transactions/tx_form.html", {
        "project": project, "form": form,
        "title": _("Project Income"),
        "tx_type": "project_income",
    })


@login_required
def asset_purchase(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    denied = _require_edit(request, project)
    if denied:
        return denied

    if request.method == "POST":
        form = tx_forms.AssetPurchaseForm(project, request.POST)
        if form.is_valid():
            d = form.cleaned_data
            try:
                svc.asset_purchase(
                    project=project, user=request.user,
                    date=d["date"], asset_account=d["asset_account"],
                    amount=d["amount"], cashbox=d["cashbox"],
                    description=d.get("description", ""),
                    currency=d.get("currency"), exchange_rate=d.get("exchange_rate") or 1,
                )
                messages.success(request, _("Asset purchase recorded."))
                return _dash_redirect(project_pk)
            except ValueError as e:
                messages.error(request, str(e))
    else:
        form = tx_forms.AssetPurchaseForm(project, initial={"date": timezone.now().date()})

    return render(request, "transactions/tx_form.html", {
        "project": project, "form": form,
        "title": _("Asset Purchase"),
        "tx_type": "asset_purchase",
    })


@login_required
def pay_salary(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    denied = _require_edit(request, project)
    if denied:
        return denied

    if request.method == "POST":
        form = tx_forms.PaySalaryForm(project, request.POST)
        if form.is_valid():
            d = form.cleaned_data
            try:
                svc.pay_salary(
                    project=project, user=request.user,
                    date=d["date"], employee=d["employee"],
                    days_or_months=d["days_or_months"], cashbox=d["cashbox"],
                    description=d.get("description", ""),
                    currency=d.get("currency"), exchange_rate=d.get("exchange_rate") or 1,
                )
                messages.success(request, _("Salary payment recorded."))
                return _dash_redirect(project_pk)
            except ValueError as e:
                messages.error(request, str(e))
    else:
        form = tx_forms.PaySalaryForm(project, initial={"date": timezone.now().date(), "days_or_months": 1})

    return render(request, "transactions/tx_form.html", {
        "project": project, "form": form,
        "title": _("Pay Salary"),
        "tx_type": "pay_salary",
    })


@login_required
def manual_je(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    denied = _require_edit(request, project)
    if denied:
        return denied

    accounts = Account.objects.filter(project=project, is_active=True).order_by("code")
    from core.models import Currency
    currencies = Currency.objects.filter(is_active=True)
    base_currency = project.base_currency

    if request.method == "POST":
        date = request.POST.get("date")
        description = request.POST.get("description", "")
        account_ids = request.POST.getlist("account_id")
        debits = request.POST.getlist("debit")
        credits = request.POST.getlist("credit")
        currency_ids = request.POST.getlist("currency_id")
        exchange_rates = request.POST.getlist("exchange_rate")
        line_descs = request.POST.getlist("line_desc")

        lines = []
        for i, acc_id in enumerate(account_ids):
            if acc_id:
                lines.append({
                    "account_id": acc_id,
                    "debit": debits[i] or 0,
                    "credit": credits[i] or 0,
                    "currency_id": currency_ids[i] if i < len(currency_ids) else None,
                    "exchange_rate": exchange_rates[i] if i < len(exchange_rates) else 1,
                    "description": line_descs[i] if i < len(line_descs) else "",
                })

        from decimal import Decimal
        total_debit = sum(Decimal(str(l["debit"])) for l in lines)
        total_credit = sum(Decimal(str(l["credit"])) for l in lines)

        if total_debit != total_credit:
            messages.error(request, _("Journal entry is not balanced. Total debit must equal total credit."))
        elif not lines:
            messages.error(request, _("At least one line is required."))
        else:
            svc.manual_journal_entry(project, request.user, date, description, lines)
            messages.success(request, _("Journal entry recorded."))
            return _dash_redirect(project_pk)

    return render(request, "transactions/manual_je.html", {
        "project": project,
        "title": _("Manual Journal Entry"),
        "accounts": accounts,
        "currencies": currencies,
        "base_currency": base_currency,
    })


@login_required
def vendor_advance_settlement(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    denied = _require_edit(request, project)
    if denied:
        return denied

    initial_vendor_pk = request.GET.get("vendor")
    initial = {"date": timezone.now().date(), "use_base_currency": True}
    if initial_vendor_pk:
        try:
            initial["vendor"] = Vendor.objects.get(pk=initial_vendor_pk, project=project)
        except Vendor.DoesNotExist:
            pass

    if request.method == "POST":
        form = tx_forms.VendorAdvanceSettlementForm(project, request.POST)
        if form.is_valid():
            d = form.cleaned_data
            use_base = d.get("use_base_currency", True)
            currency = None if use_base else d.get("currency")
            exchange_rate = 1 if use_base else (d.get("exchange_rate") or 1)
            try:
                svc.vendor_advance_settlement(
                    project=project, user=request.user,
                    date=d["date"], vendor=d["vendor"],
                    amount=d["amount"],
                    description=d.get("description", ""),
                    currency=currency, exchange_rate=exchange_rate,
                )
                messages.success(request, _("Vendor advance settlement recorded."))
                return _dash_redirect(project_pk)
            except ValueError as e:
                messages.error(request, str(e))
    else:
        form = tx_forms.VendorAdvanceSettlementForm(project, initial=initial)

    return render(request, "transactions/tx_form.html", {
        "project": project, "form": form,
        "title": _("Vendor Advance Settlement"),
        "tx_type": "vendor_advance_settlement",
    })


@login_required
def vendor_direct_payment(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    denied = _require_edit(request, project)
    if denied:
        return denied

    initial_vendor_pk = request.GET.get("vendor")
    initial = {"date": timezone.now().date(), "use_base_currency": True}
    if initial_vendor_pk:
        try:
            initial["vendor"] = Vendor.objects.get(pk=initial_vendor_pk, project=project)
        except Vendor.DoesNotExist:
            pass

    if request.method == "POST":
        form = tx_forms.VendorDirectPaymentForm(project, request.POST)
        if form.is_valid():
            d = form.cleaned_data
            use_base = d.get("use_base_currency", True)
            currency = None if use_base else d.get("currency")
            exchange_rate = 1 if use_base else (d.get("exchange_rate") or 1)
            try:
                svc.vendor_direct_payment(
                    project=project, user=request.user,
                    date=d["date"], vendor=d["vendor"],
                    expense_account=d["expense_account"],
                    amount=d["amount"], cashbox=d["cashbox"],
                    description=d.get("description", ""),
                    currency=currency, exchange_rate=exchange_rate,
                )
                messages.success(request, _("Vendor direct payment recorded."))
                return _dash_redirect(project_pk)
            except ValueError as e:
                messages.error(request, str(e))
    else:
        form = tx_forms.VendorDirectPaymentForm(project, initial=initial)

    return render(request, "transactions/tx_form.html", {
        "project": project, "form": form,
        "title": _("Vendor Direct Payment"),
        "tx_type": "vendor_direct_payment",
    })


@login_required
def vendor_refund(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    denied = _require_edit(request, project)
    if denied:
        return denied

    initial_vendor_pk = request.GET.get("vendor")
    initial = {"date": timezone.now().date(), "use_base_currency": True}
    if initial_vendor_pk:
        try:
            initial["vendor"] = Vendor.objects.get(pk=initial_vendor_pk, project=project)
        except Vendor.DoesNotExist:
            pass

    if request.method == "POST":
        form = tx_forms.VendorRefundForm(project, request.POST)
        if form.is_valid():
            d = form.cleaned_data
            use_base = d.get("use_base_currency", True)
            currency = None if use_base else d.get("currency")
            exchange_rate = 1 if use_base else (d.get("exchange_rate") or 1)
            svc.vendor_refund(
                project=project, user=request.user,
                date=d["date"], vendor=d["vendor"],
                amount=d["amount"], cashbox=d["cashbox"],
                description=d.get("description", ""),
                currency=currency, exchange_rate=exchange_rate,
            )
            messages.success(request, _("Vendor refund recorded."))
            return _dash_redirect(project_pk)
    else:
        form = tx_forms.VendorRefundForm(project, initial=initial)

    return render(request, "transactions/tx_form.html", {
        "project": project, "form": form,
        "title": _("Vendor Refund"),
        "tx_type": "vendor_refund",
    })
