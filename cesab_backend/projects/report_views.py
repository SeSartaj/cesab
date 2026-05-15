"""
Financial report views for a project.

Each report follows the same pattern:
  1. Access-check via _require_project_access.
  2. Parse optional date_from / date_to GET params.
  3. Query journal lines (always via JournalLine.objects.active() so that
     corrected / voided entries are silently excluded).
  4. Render a template.

Purchase and tax reports additionally use the document layer
(VendorBill / CustomerInvoice) so that the per-supplier and per-tax
breakdowns match what operators expect from their posted documents.
"""

from collections import defaultdict
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _

from coa.models import Account
from documents.models import (
    POSTED,
    CustomerInvoice,
    CustomerInvoiceLine,
    Tax,
    VendorBill,
    VendorBillLine,
)
from journal.models import JournalLine

from .models import Project
from .views import _project_permission_ctx, _require_project_access


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_dates(request):
    return request.GET.get("date_from", ""), request.GET.get("date_to", "")


def _filter_by_date(qs, date_from, date_to, date_field="journal_entry__date"):
    if date_from:
        qs = qs.filter(**{f"{date_field}__gte": date_from})
    if date_to:
        qs = qs.filter(**{f"{date_field}__lte": date_to})
    return qs


def _build_debit_credit_maps(line_qs):
    debit_map = {
        r["account_id"]: r["total"] or Decimal("0")
        for r in line_qs.values("account_id").annotate(total=Sum("debit"))
    }
    credit_map = {
        r["account_id"]: r["total"] or Decimal("0")
        for r in line_qs.values("account_id").annotate(total=Sum("credit"))
    }
    return debit_map, credit_map


def _account_balance(acc, debit_map, credit_map):
    d = debit_map.get(acc.pk, Decimal("0"))
    c = credit_map.get(acc.pk, Decimal("0"))
    if acc.account_type in ("asset", "expense"):
        return d - c
    return c - d


def _active_bills(project, date_from, date_to):
    """Posted, non-reversed, non-reversal vendor bills for *project*."""
    qs = VendorBill.objects.filter(
        project=project,
        status=POSTED,
        reversal_of__isnull=True,
        reversed_by__isnull=True,
    )
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    return qs


def _active_invoices(project, date_from, date_to):
    """Posted, non-reversed, non-reversal customer invoices for *project*."""
    qs = CustomerInvoice.objects.filter(
        project=project,
        status=POSTED,
        reversal_of__isnull=True,
        reversed_by__isnull=True,
    )
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    return qs


# ---------------------------------------------------------------------------
# Profit & Loss
# ---------------------------------------------------------------------------

@login_required
def profit_and_loss(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if not _require_project_access(request.user, project):
        messages.error(request, _("You do not have access to this project."))
        return redirect("projects:list")

    date_from, date_to = _parse_dates(request)

    base_qs = JournalLine.objects.active().filter(account__project=project)
    line_qs = _filter_by_date(base_qs, date_from, date_to)
    debit_map, credit_map = _build_debit_credit_maps(line_qs)

    # Income  (credit-normal accounts)
    income_rows = []
    total_income = Decimal("0")
    for acc in Account.objects.filter(
        project=project, account_type="income", is_active=True
    ).order_by("code"):
        bal = _account_balance(acc, debit_map, credit_map)
        if bal:
            income_rows.append({"account": acc, "balance": bal})
            total_income += bal

    # Expense (debit-normal accounts)
    expense_rows = []
    total_expense = Decimal("0")
    for acc in Account.objects.filter(
        project=project, account_type="expense", is_active=True
    ).order_by("code"):
        bal = _account_balance(acc, debit_map, credit_map)
        if bal:
            expense_rows.append({"account": acc, "balance": bal})
            total_expense += bal

    net_profit = total_income - total_expense

    return render(request, "projects/reports/profit_and_loss.html", {
        "project": project,
        "income_rows": income_rows,
        "expense_rows": expense_rows,
        "total_income": total_income,
        "total_expense": total_expense,
        "net_profit": net_profit,
        "date_from": date_from,
        "date_to": date_to,
        **_project_permission_ctx(request.user, project),
    })


# ---------------------------------------------------------------------------
# Balance Sheet
# ---------------------------------------------------------------------------

@login_required
def balance_sheet(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if not _require_project_access(request.user, project):
        messages.error(request, _("You do not have access to this project."))
        return redirect("projects:list")

    # Balance sheet is a snapshot (as-of date) — only date_to is applied.
    # date_from is accepted in the form but used only to communicate the
    # reporting period to the user; it does not filter the balance sheet data.
    date_from, date_to = _parse_dates(request)

    base_qs = JournalLine.objects.active().filter(account__project=project)
    if date_to:
        base_qs = base_qs.filter(journal_entry__date__lte=date_to)
    debit_map, credit_map = _build_debit_credit_maps(base_qs)

    def _rows(account_type):
        rows = []
        total = Decimal("0")
        for acc in Account.objects.filter(
            project=project, account_type=account_type, is_active=True
        ).order_by("code"):
            bal = _account_balance(acc, debit_map, credit_map)
            if bal:
                rows.append({"account": acc, "balance": bal})
                total += bal
        return rows, total

    asset_rows, total_assets = _rows("asset")
    liability_rows, total_liabilities = _rows("liability")
    equity_rows, total_equity = _rows("equity")

    # Retained earnings = net of income - expense (implicit equity)
    income_total = Decimal("0")
    for acc in Account.objects.filter(project=project, account_type="income", is_active=True):
        income_total += _account_balance(acc, debit_map, credit_map)

    expense_total = Decimal("0")
    for acc in Account.objects.filter(project=project, account_type="expense", is_active=True):
        expense_total += _account_balance(acc, debit_map, credit_map)

    retained_earnings = income_total - expense_total
    total_equity_inc_retained = total_equity + retained_earnings
    total_liab_equity = total_liabilities + total_equity_inc_retained
    is_balanced = total_assets == total_liab_equity

    return render(request, "projects/reports/balance_sheet.html", {
        "project": project,
        "asset_rows": asset_rows,
        "liability_rows": liability_rows,
        "equity_rows": equity_rows,
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "total_equity": total_equity,
        "retained_earnings": retained_earnings,
        "total_equity_inc_retained": total_equity_inc_retained,
        "total_liab_equity": total_liab_equity,
        "is_balanced": is_balanced,
        "date_from": date_from,
        "date_to": date_to,
        **_project_permission_ctx(request.user, project),
    })


# ---------------------------------------------------------------------------
# Purchase & Cost Report
# ---------------------------------------------------------------------------

@login_required
def purchase_report(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if not _require_project_access(request.user, project):
        messages.error(request, _("You do not have access to this project."))
        return redirect("projects:list")

    date_from, date_to = _parse_dates(request)
    bills = _active_bills(project, date_from, date_to).select_related("contact", "currency")

    # --- Supplier-wise summary ---
    supplier_map: dict = {}
    for bill in bills:
        name = bill.contact.name
        if name not in supplier_map:
            supplier_map[name] = {
                "name": name,
                "count": 0,
                "subtotal": Decimal("0"),
                "tax": Decimal("0"),
                "total": Decimal("0"),
            }
        supplier_map[name]["count"] += 1
        supplier_map[name]["subtotal"] += bill.total_subtotal()
        supplier_map[name]["tax"] += bill.total_tax()
        supplier_map[name]["total"] += bill.total_amount()

    supplier_rows = sorted(supplier_map.values(), key=lambda r: r["total"], reverse=True)
    total_purchases_subtotal = sum(r["subtotal"] for r in supplier_rows)
    total_purchases_tax = sum(r["tax"] for r in supplier_rows)
    total_purchases = sum(r["total"] for r in supplier_rows)

    # --- Expense-account breakdown ---
    bill_pks = list(bills.values_list("pk", flat=True))
    account_map: dict = {}
    for line in VendorBillLine.objects.filter(bill__in=bill_pks).select_related("account"):
        acc = line.account
        if acc.pk not in account_map:
            account_map[acc.pk] = {
                "account": acc,
                "subtotal": Decimal("0"),
                "tax": Decimal("0"),
            }
        account_map[acc.pk]["subtotal"] += line.subtotal()
        account_map[acc.pk]["tax"] += line.tax_amount()

    account_rows = sorted(
        [
            {**v, "total": v["subtotal"] + v["tax"]}
            for v in account_map.values()
        ],
        key=lambda r: r["total"],
        reverse=True,
    )

    return render(request, "projects/reports/purchase_report.html", {
        "project": project,
        "supplier_rows": supplier_rows,
        "account_rows": account_rows,
        "total_purchases_subtotal": total_purchases_subtotal,
        "total_purchases_tax": total_purchases_tax,
        "total_purchases": total_purchases,
        "date_from": date_from,
        "date_to": date_to,
        **_project_permission_ctx(request.user, project),
    })


# ---------------------------------------------------------------------------
# VAT / Tax Report
# ---------------------------------------------------------------------------

@login_required
def tax_report(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if not _require_project_access(request.user, project):
        messages.error(request, _("You do not have access to this project."))
        return redirect("projects:list")

    date_from, date_to = _parse_dates(request)

    bills = _active_bills(project, date_from, date_to)
    invoices = _active_invoices(project, date_from, date_to)

    # Input VAT — from vendor bill lines
    input_by_tax: dict = {}
    for line in VendorBillLine.objects.filter(bill__in=bills).select_related("tax"):
        if not line.tax_id:
            continue
        if line.tax_id not in input_by_tax:
            input_by_tax[line.tax_id] = {
                "tax": line.tax,
                "taxable_base": Decimal("0"),
                "tax_amount": Decimal("0"),
            }
        input_by_tax[line.tax_id]["taxable_base"] += line.subtotal()
        input_by_tax[line.tax_id]["tax_amount"] += line.tax_amount()

    # Output VAT — from customer invoice lines
    output_by_tax: dict = {}
    for line in CustomerInvoiceLine.objects.filter(invoice__in=invoices).select_related("tax"):
        if not line.tax_id:
            continue
        if line.tax_id not in output_by_tax:
            output_by_tax[line.tax_id] = {
                "tax": line.tax,
                "taxable_base": Decimal("0"),
                "tax_amount": Decimal("0"),
            }
        output_by_tax[line.tax_id]["taxable_base"] += line.subtotal()
        output_by_tax[line.tax_id]["tax_amount"] += line.tax_amount()

    # Merge into combined rows keyed by tax
    all_tax_ids = sorted(
        set(input_by_tax) | set(output_by_tax),
        key=lambda tid: (
            input_by_tax.get(tid) or output_by_tax.get(tid)
        )["tax"].name,
    )

    tax_rows = []
    total_input_base = Decimal("0")
    total_input_vat = Decimal("0")
    total_output_base = Decimal("0")
    total_output_vat = Decimal("0")

    for tid in all_tax_ids:
        inp = input_by_tax.get(tid)
        out = output_by_tax.get(tid)
        tax_obj = (inp or out)["tax"]
        if inp is None:
            inp = {"tax": tax_obj, "taxable_base": Decimal("0"), "tax_amount": Decimal("0")}
        if out is None:
            out = {"tax": tax_obj, "taxable_base": Decimal("0"), "tax_amount": Decimal("0")}
        tax_obj = inp["tax"] if inp["tax_amount"] else out["tax"]
        net = out["tax_amount"] - inp["tax_amount"]  # positive = payable to govt
        tax_rows.append({
            "tax": tax_obj,
            "input_base": inp["taxable_base"],
            "input_vat": inp["tax_amount"],
            "output_base": out["taxable_base"],
            "output_vat": out["tax_amount"],
            "net": net,
        })
        total_input_base += inp["taxable_base"]
        total_input_vat += inp["tax_amount"]
        total_output_base += out["taxable_base"]
        total_output_vat += out["tax_amount"]

    net_vat = total_output_vat - total_input_vat  # positive = payable, negative = refundable

    return render(request, "projects/reports/tax_report.html", {
        "project": project,
        "tax_rows": tax_rows,
        "total_input_base": total_input_base,
        "total_input_vat": total_input_vat,
        "total_output_base": total_output_base,
        "total_output_vat": total_output_vat,
        "net_vat": net_vat,
        "date_from": date_from,
        "date_to": date_to,
        **_project_permission_ctx(request.user, project),
    })
