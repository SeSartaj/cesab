"""
Tests for the documents app — services, models, and basic view access.

Test classes
────────────
TaxModelTests          — Tax model helpers
BillLineTests          — VendorBillLine / CustomerInvoiceLine calculations
PostVendorBillTests    — post_vendor_bill validation & journal entries
PostCustomerInvoiceTests — post_customer_invoice validation & journal entries
PostPaymentTests       — post_payment validation & journal entries
PostReceiptTests       — post_receipt validation & journal entries
ReversalTests          — reverse_* functions: creates reversal, guards
"""
from decimal import Decimal
from datetime import date

from django.test import TestCase

from auth_users.models import User
from cash.models import Cashbox
from coa.models import Account
from coa.services import create_standard_coa
from core.models import Currency
from journal.models import JournalEntry, JournalLine
from projects.models import Project
from vendors.models import Contact

from documents.models import (
    Tax, VendorBill, VendorBillLine,
    CustomerInvoice, CustomerInvoiceLine,
    Payment, Receipt, DRAFT, POSTED,
)
from documents.services import (
    post_vendor_bill, post_customer_invoice,
    post_payment, post_receipt,
    reverse_vendor_bill, reverse_customer_invoice,
    reverse_payment, reverse_receipt,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_currency(code, name="", symbol=""):
    c, _ = Currency.objects.get_or_create(
        code=code, defaults={"name": name or code, "symbol": symbol, "is_active": True}
    )
    return c


def _make_user(username="tester"):
    u, _ = User.objects.get_or_create(username=username)
    return u


def _make_project(base_currency, name="TestProject"):
    proj = Project.objects.create(
        name=name,
        base_currency=base_currency,
    )
    create_standard_coa(proj)
    return proj


def _make_cashbox(project, name="Main Cash", currency=None):
    currency = currency or project.base_currency
    parent = Account.objects.filter(project=project, code="1100").first()
    account = Account.objects.create(
        project=project,
        code=f"1101-{name[:4]}",
        name=f"Cash – {name}",
        account_type="asset",
        parent=parent,
    )
    # Seed the cashbox account with 1 000 000
    _seed_account(project, account, currency, Decimal("1000000"))
    return Cashbox.objects.create(project=project, name=name, account=account, currency=currency)


def _seed_account(project, account, currency, amount_bc):
    """Inject balance into an account so payment balance-checks pass."""
    je = JournalEntry.objects.create(
        project=project, date=date(2025, 1, 1),
        description="Seed funds", transaction_type="manual", created_by=_make_user(),
    )
    JournalLine.objects.create(
        journal_entry=je, account=account,
        debit=amount_bc, credit=Decimal("0"),
        transaction_currency=currency, exchange_rate=Decimal("1"),
        debit_tc=amount_bc, credit_tc=Decimal("0"),
    )


def _make_vendor(project, name="ACME Vendor"):
    contact = Contact.objects.create(
        project=project, name=name, contact_type=Contact.VENDOR
    )
    # Find or create the payable and advance accounts
    payable_parent = Account.objects.filter(project=project, code="2100").first()
    adv_parent = Account.objects.filter(project=project, code="1300").first()

    payable_acc = Account.objects.create(
        project=project, code=f"2101-{name[:4]}", name=f"Payable – {name}",
        account_type="liability", parent=payable_parent,
    )
    adv_acc = Account.objects.create(
        project=project, code=f"1301-{name[:4]}", name=f"Advance – {name}",
        account_type="asset", parent=adv_parent,
    )
    contact.payable_account = payable_acc
    contact.advance_account = adv_acc
    contact.save()
    return contact


def _make_customer(project, name="Widget Co"):
    contact = Contact.objects.create(
        project=project, name=name, contact_type=Contact.CUSTOMER
    )
    rec_parent = Account.objects.filter(project=project, code="1200").first()
    rec_acc = Account.objects.create(
        project=project, code=f"1201-{name[:4]}", name=f"Receivable – {name}",
        account_type="asset", parent=rec_parent,
    )
    contact.receivable_account = rec_acc
    contact.save()
    return contact


def _expense_account(project):
    parent = Account.objects.filter(project=project, code="5000").first()
    acc, _ = Account.objects.get_or_create(
        project=project, code="5001-TEST",
        defaults={"name": "Test Expense", "account_type": "expense", "parent": parent},
    )
    return acc


def _revenue_account(project):
    parent = Account.objects.filter(project=project, code="4000").first()
    acc, _ = Account.objects.get_or_create(
        project=project, code="4001-TEST",
        defaults={"name": "Test Revenue", "account_type": "income", "parent": parent},
    )
    return acc


def _tax_account(project, code="2300"):
    acc, _ = Account.objects.get_or_create(
        project=project, code=code,
        defaults={"name": "VAT Payable", "account_type": "liability"},
    )
    return acc


# ---------------------------------------------------------------------------
# 1. Tax model
# ---------------------------------------------------------------------------

class TaxModelTests(TestCase):

    def setUp(self):
        self.base = _make_currency("AFN", "Afghani", "؋")
        self.project = _make_project(self.base)
        self.user = _make_user()

    def test_rate_percent(self):
        tax = Tax(project=self.project, name="VAT10",
                  rate=Decimal("0.1000"),
                  account=_tax_account(self.project))
        self.assertAlmostEqual(float(tax.rate_percent()), 10.0, places=2)

    def test_str_representation(self):
        tax = Tax(project=self.project, name="WHT5",
                  rate=Decimal("0.0500"),
                  account=_tax_account(self.project))
        self.assertIn("5.00", str(tax))
        self.assertIn("WHT5", str(tax))


# ---------------------------------------------------------------------------
# 2. Line calculation helpers
# ---------------------------------------------------------------------------

class BillLineTests(TestCase):

    def setUp(self):
        self.base = _make_currency("AFN")
        self.project = _make_project(self.base)
        self.vendor = _make_vendor(self.project)
        self.user = _make_user()
        self.currency = self.base
        self.bill = VendorBill.objects.create(
            project=self.project, contact=self.vendor,
            date=date(2025, 6, 1), currency=self.currency,
            exchange_rate=Decimal("1"), created_by=self.user,
        )
        self.expense = _expense_account(self.project)
        self.tax_acc = _tax_account(self.project)
        self.tax = Tax.objects.create(
            project=self.project, name="VAT10",
            rate=Decimal("0.10"), account=self.tax_acc,
        )

    def test_subtotal_no_tax(self):
        line = VendorBillLine(bill=self.bill, account=self.expense,
                              quantity=Decimal("2"), unit_price=Decimal("100"))
        self.assertEqual(line.subtotal(), Decimal("200.00"))

    def test_tax_amount(self):
        line = VendorBillLine(bill=self.bill, account=self.expense,
                              quantity=Decimal("3"), unit_price=Decimal("100"),
                              tax=self.tax)
        self.assertEqual(line.tax_amount(), Decimal("30.00"))

    def test_line_total_with_tax(self):
        line = VendorBillLine(bill=self.bill, account=self.expense,
                              quantity=Decimal("1"), unit_price=Decimal("200"),
                              tax=self.tax)
        self.assertEqual(line.total(), Decimal("220.00"))

    def test_line_total_no_tax(self):
        line = VendorBillLine(bill=self.bill, account=self.expense,
                              quantity=Decimal("1"), unit_price=Decimal("200"))
        self.assertEqual(line.total(), Decimal("200.00"))

    def test_bill_totals(self):
        VendorBillLine.objects.create(
            bill=self.bill, account=self.expense,
            quantity=Decimal("2"), unit_price=Decimal("100"), tax=self.tax,
        )
        VendorBillLine.objects.create(
            bill=self.bill, account=self.expense,
            quantity=Decimal("1"), unit_price=Decimal("50"),
        )
        self.assertEqual(self.bill.total_subtotal(), Decimal("250.00"))
        self.assertEqual(self.bill.total_tax(), Decimal("20.00"))  # 200 × 10%
        self.assertEqual(self.bill.total_amount(), Decimal("270.00"))

    def test_number_auto_generated(self):
        self.assertTrue(self.bill.number.startswith("BILL-"))

    def test_is_draft_on_new_bill(self):
        self.assertTrue(self.bill.is_draft)
        self.assertFalse(self.bill.is_posted)


# ---------------------------------------------------------------------------
# 3. Post Vendor Bill
# ---------------------------------------------------------------------------

class PostVendorBillTests(TestCase):

    def setUp(self):
        self.base = _make_currency("AFN")
        self.project = _make_project(self.base)
        self.user = _make_user()
        self.vendor = _make_vendor(self.project)
        self.expense = _expense_account(self.project)
        self.tax_acc = _tax_account(self.project)
        self.tax = Tax.objects.create(
            project=self.project, name="VAT10",
            rate=Decimal("0.10"), account=self.tax_acc,
        )

    def _make_bill(self, currency=None, rate=Decimal("1")):
        currency = currency or self.base
        bill = VendorBill.objects.create(
            project=self.project, contact=self.vendor,
            date=date(2025, 6, 1), currency=currency,
            exchange_rate=rate, created_by=self.user,
        )
        return bill

    def test_post_simple_bill(self):
        bill = self._make_bill()
        VendorBillLine.objects.create(
            bill=bill, account=self.expense,
            quantity=Decimal("1"), unit_price=Decimal("1000"),
        )
        result = post_vendor_bill(bill, self.user)
        self.assertEqual(result.status, POSTED)
        self.assertIsNotNone(result.journal_entry)

    def test_journal_entry_lines_created(self):
        bill = self._make_bill()
        VendorBillLine.objects.create(
            bill=bill, account=self.expense,
            quantity=Decimal("2"), unit_price=Decimal("500"),
        )
        post_vendor_bill(bill, self.user)
        je = bill.journal_entry
        lines = list(je.lines.all())
        # 1 expense line + 1 payable line
        self.assertEqual(len(lines), 2)

    def test_journal_entry_balanced(self):
        bill = self._make_bill()
        VendorBillLine.objects.create(
            bill=bill, account=self.expense,
            quantity=Decimal("1"), unit_price=Decimal("800"), tax=self.tax,
        )
        post_vendor_bill(bill, self.user)
        je = bill.journal_entry
        from django.db.models import Sum
        agg = je.lines.aggregate(d=Sum("debit"), c=Sum("credit"))
        self.assertEqual(agg["d"], agg["c"])

    def test_tax_line_created(self):
        bill = self._make_bill()
        VendorBillLine.objects.create(
            bill=bill, account=self.expense,
            quantity=Decimal("1"), unit_price=Decimal("1000"), tax=self.tax,
        )
        post_vendor_bill(bill, self.user)
        lines = list(bill.journal_entry.lines.all())
        # expense + tax + payable = 3
        self.assertEqual(len(lines), 3)
        tax_line = next(l for l in lines if l.account == self.tax_acc)
        self.assertEqual(tax_line.debit_tc, Decimal("100.00"))

    def test_raises_on_empty_bill(self):
        bill = self._make_bill()
        with self.assertRaises(ValueError, msg="Cannot post a bill with no lines."):
            post_vendor_bill(bill, self.user)

    def test_raises_if_already_posted(self):
        bill = self._make_bill()
        VendorBillLine.objects.create(
            bill=bill, account=self.expense,
            quantity=Decimal("1"), unit_price=Decimal("100"),
        )
        post_vendor_bill(bill, self.user)
        with self.assertRaises(ValueError):
            post_vendor_bill(bill, self.user)

    def test_raises_if_no_payable_account(self):
        vendor = Contact.objects.create(
            project=self.project, name="NoAcct", contact_type=Contact.VENDOR
        )
        bill = VendorBill.objects.create(
            project=self.project, contact=vendor,
            date=date(2025, 6, 1), currency=self.base,
            exchange_rate=Decimal("1"), created_by=self.user,
        )
        VendorBillLine.objects.create(
            bill=bill, account=self.expense,
            quantity=Decimal("1"), unit_price=Decimal("100"),
        )
        with self.assertRaises(ValueError):
            post_vendor_bill(bill, self.user)

    def test_foreign_currency_bill(self):
        usd = _make_currency("USD")
        bill = self._make_bill(currency=usd, rate=Decimal("70"))
        VendorBillLine.objects.create(
            bill=bill, account=self.expense,
            quantity=Decimal("1"), unit_price=Decimal("100"),  # 100 USD
        )
        post_vendor_bill(bill, self.user)
        je = bill.journal_entry
        payable_line = je.lines.get(account=self.vendor.payable_account)
        # 100 TC × 70 rate = 7000 BC
        self.assertEqual(payable_line.credit, Decimal("7000.00"))
        self.assertEqual(payable_line.credit_tc, Decimal("100.00"))


# ---------------------------------------------------------------------------
# 4. Post Customer Invoice
# ---------------------------------------------------------------------------

class PostCustomerInvoiceTests(TestCase):

    def setUp(self):
        self.base = _make_currency("AFN")
        self.project = _make_project(self.base)
        self.user = _make_user()
        self.customer = _make_customer(self.project)
        self.revenue = _revenue_account(self.project)
        self.tax_acc = _tax_account(self.project, code="2301")
        self.tax = Tax.objects.create(
            project=self.project, name="VAT15",
            rate=Decimal("0.15"), account=self.tax_acc,
        )

    def _make_invoice(self, currency=None, rate=Decimal("1")):
        currency = currency or self.base
        return CustomerInvoice.objects.create(
            project=self.project, contact=self.customer,
            date=date(2025, 6, 1), currency=currency,
            exchange_rate=rate, created_by=self.user,
        )

    def test_post_simple_invoice(self):
        inv = self._make_invoice()
        CustomerInvoiceLine.objects.create(
            invoice=inv, account=self.revenue,
            quantity=Decimal("1"), unit_price=Decimal("2000"),
        )
        result = post_customer_invoice(inv, self.user)
        self.assertEqual(result.status, POSTED)
        self.assertIsNotNone(result.journal_entry)

    def test_invoice_je_balanced(self):
        inv = self._make_invoice()
        CustomerInvoiceLine.objects.create(
            invoice=inv, account=self.revenue,
            quantity=Decimal("1"), unit_price=Decimal("1500"), tax=self.tax,
        )
        post_customer_invoice(inv, self.user)
        from django.db.models import Sum
        agg = inv.journal_entry.lines.aggregate(d=Sum("debit"), c=Sum("credit"))
        self.assertEqual(agg["d"], agg["c"])

    def test_revenue_and_tax_lines_created(self):
        inv = self._make_invoice()
        CustomerInvoiceLine.objects.create(
            invoice=inv, account=self.revenue,
            quantity=Decimal("1"), unit_price=Decimal("1000"), tax=self.tax,
        )
        post_customer_invoice(inv, self.user)
        lines = list(inv.journal_entry.lines.all())
        # receivable + revenue + tax = 3
        self.assertEqual(len(lines), 3)

    def test_raises_on_empty_invoice(self):
        inv = self._make_invoice()
        with self.assertRaises(ValueError):
            post_customer_invoice(inv, self.user)

    def test_raises_if_no_receivable_account(self):
        customer = Contact.objects.create(
            project=self.project, name="NoRec", contact_type=Contact.CUSTOMER
        )
        inv = CustomerInvoice.objects.create(
            project=self.project, contact=customer,
            date=date(2025, 6, 1), currency=self.base,
            exchange_rate=Decimal("1"), created_by=self.user,
        )
        CustomerInvoiceLine.objects.create(
            invoice=inv, account=self.revenue,
            quantity=Decimal("1"), unit_price=Decimal("100"),
        )
        with self.assertRaises(ValueError):
            post_customer_invoice(inv, self.user)

    def test_invoice_number_format(self):
        inv = self._make_invoice()
        self.assertTrue(inv.number.startswith("INV-"))


# ---------------------------------------------------------------------------
# 5. Post Payment
# ---------------------------------------------------------------------------

class PostPaymentTests(TestCase):

    def setUp(self):
        self.base = _make_currency("AFN")
        self.project = _make_project(self.base)
        self.user = _make_user()
        self.vendor = _make_vendor(self.project)
        self.cashbox = _make_cashbox(self.project, "AFN Cash", self.base)
        self.expense = _expense_account(self.project)

    def _make_bill_posted(self, amount=Decimal("1000")):
        bill = VendorBill.objects.create(
            project=self.project, contact=self.vendor,
            date=date(2025, 6, 1), currency=self.base,
            exchange_rate=Decimal("1"), created_by=self.user,
        )
        VendorBillLine.objects.create(
            bill=bill, account=self.expense,
            quantity=Decimal("1"), unit_price=amount,
        )
        return post_vendor_bill(bill, self.user)

    def test_post_payment_same_currency(self):
        pay = Payment.objects.create(
            project=self.project, contact=self.vendor,
            date=date(2025, 6, 10), currency=self.base,
            exchange_rate=Decimal("1"), amount=Decimal("500"),
            cashbox=self.cashbox, created_by=self.user,
        )
        result = post_payment(pay, self.user)
        self.assertEqual(result.status, POSTED)
        self.assertIsNotNone(result.journal_entry)

    def test_payment_je_balanced(self):
        pay = Payment.objects.create(
            project=self.project, contact=self.vendor,
            date=date(2025, 6, 10), currency=self.base,
            exchange_rate=Decimal("1"), amount=Decimal("300"),
            cashbox=self.cashbox, created_by=self.user,
        )
        post_payment(pay, self.user)
        from django.db.models import Sum
        agg = pay.journal_entry.lines.aggregate(d=Sum("debit"), c=Sum("credit"))
        self.assertEqual(agg["d"], agg["c"])

    def test_payment_number_format(self):
        pay = Payment.objects.create(
            project=self.project, contact=self.vendor,
            date=date(2025, 6, 10), currency=self.base,
            exchange_rate=Decimal("1"), amount=Decimal("100"),
            cashbox=self.cashbox, created_by=self.user,
        )
        self.assertTrue(pay.number.startswith("PAY-"))

    def test_raises_if_insufficient_balance(self):
        pay = Payment.objects.create(
            project=self.project, contact=self.vendor,
            date=date(2025, 6, 10), currency=self.base,
            exchange_rate=Decimal("1"), amount=Decimal("9999999"),
            cashbox=self.cashbox, created_by=self.user,
        )
        with self.assertRaises(ValueError, msg="Insufficient balance"):
            post_payment(pay, self.user)

    def test_raises_if_already_posted(self):
        pay = Payment.objects.create(
            project=self.project, contact=self.vendor,
            date=date(2025, 6, 10), currency=self.base,
            exchange_rate=Decimal("1"), amount=Decimal("100"),
            cashbox=self.cashbox, created_by=self.user,
        )
        post_payment(pay, self.user)
        with self.assertRaises(ValueError):
            post_payment(pay, self.user)

    def test_foreign_currency_payment(self):
        usd = _make_currency("USD")
        usd_cashbox = _make_cashbox(self.project, "USD Cash", usd)
        _seed_account(self.project, usd_cashbox.account, usd, Decimal("1000"))
        pay = Payment.objects.create(
            project=self.project, contact=self.vendor,
            date=date(2025, 6, 10), currency=usd,
            exchange_rate=Decimal("70"), amount=Decimal("100"),
            cashbox=usd_cashbox, created_by=self.user,
        )
        result = post_payment(pay, self.user)
        self.assertEqual(result.status, POSTED)
        from django.db.models import Sum
        agg = pay.journal_entry.lines.aggregate(d=Sum("debit"), c=Sum("credit"))
        self.assertEqual(agg["d"], agg["c"])


# ---------------------------------------------------------------------------
# 6. Post Receipt
# ---------------------------------------------------------------------------

class PostReceiptTests(TestCase):

    def setUp(self):
        self.base = _make_currency("AFN")
        self.project = _make_project(self.base)
        self.user = _make_user()
        self.customer = _make_customer(self.project)
        self.cashbox = _make_cashbox(self.project, "AFN Cash", self.base)

    def test_post_receipt(self):
        rec = Receipt.objects.create(
            project=self.project, contact=self.customer,
            date=date(2025, 6, 10), currency=self.base,
            exchange_rate=Decimal("1"), amount=Decimal("500"),
            cashbox=self.cashbox, created_by=self.user,
        )
        result = post_receipt(rec, self.user)
        self.assertEqual(result.status, POSTED)
        self.assertIsNotNone(result.journal_entry)

    def test_receipt_je_balanced(self):
        rec = Receipt.objects.create(
            project=self.project, contact=self.customer,
            date=date(2025, 6, 10), currency=self.base,
            exchange_rate=Decimal("1"), amount=Decimal("700"),
            cashbox=self.cashbox, created_by=self.user,
        )
        post_receipt(rec, self.user)
        from django.db.models import Sum
        agg = rec.journal_entry.lines.aggregate(d=Sum("debit"), c=Sum("credit"))
        self.assertEqual(agg["d"], agg["c"])

    def test_receipt_number_format(self):
        rec = Receipt.objects.create(
            project=self.project, contact=self.customer,
            date=date(2025, 6, 10), currency=self.base,
            exchange_rate=Decimal("1"), amount=Decimal("100"),
            cashbox=self.cashbox, created_by=self.user,
        )
        self.assertTrue(rec.number.startswith("REC-"))

    def test_raises_if_no_receivable_account(self):
        customer = Contact.objects.create(
            project=self.project, name="NoRec", contact_type=Contact.CUSTOMER
        )
        rec = Receipt.objects.create(
            project=self.project, contact=customer,
            date=date(2025, 6, 10), currency=self.base,
            exchange_rate=Decimal("1"), amount=Decimal("100"),
            cashbox=self.cashbox, created_by=self.user,
        )
        with self.assertRaises(ValueError):
            post_receipt(rec, self.user)


# ---------------------------------------------------------------------------
# 7. Reversal
# ---------------------------------------------------------------------------

class ReversalTests(TestCase):

    def setUp(self):
        self.base = _make_currency("AFN")
        self.project = _make_project(self.base)
        self.user = _make_user()
        self.vendor = _make_vendor(self.project)
        self.customer = _make_customer(self.project)
        self.expense = _expense_account(self.project)
        self.revenue = _revenue_account(self.project)
        self.cashbox = _make_cashbox(self.project, "Cash", self.base)

    def _posted_bill(self):
        bill = VendorBill.objects.create(
            project=self.project, contact=self.vendor,
            date=date(2025, 6, 1), currency=self.base,
            exchange_rate=Decimal("1"), created_by=self.user,
        )
        VendorBillLine.objects.create(
            bill=bill, account=self.expense,
            quantity=Decimal("1"), unit_price=Decimal("1000"),
        )
        return post_vendor_bill(bill, self.user)

    def _posted_invoice(self):
        inv = CustomerInvoice.objects.create(
            project=self.project, contact=self.customer,
            date=date(2025, 6, 1), currency=self.base,
            exchange_rate=Decimal("1"), created_by=self.user,
        )
        CustomerInvoiceLine.objects.create(
            invoice=inv, account=self.revenue,
            quantity=Decimal("1"), unit_price=Decimal("1000"),
        )
        return post_customer_invoice(inv, self.user)

    def _posted_payment(self):
        pay = Payment.objects.create(
            project=self.project, contact=self.vendor,
            date=date(2025, 6, 5), currency=self.base,
            exchange_rate=Decimal("1"), amount=Decimal("400"),
            cashbox=self.cashbox, created_by=self.user,
        )
        return post_payment(pay, self.user)

    def _posted_receipt(self):
        rec = Receipt.objects.create(
            project=self.project, contact=self.customer,
            date=date(2025, 6, 5), currency=self.base,
            exchange_rate=Decimal("1"), amount=Decimal("300"),
            cashbox=self.cashbox, created_by=self.user,
        )
        return post_receipt(rec, self.user)

    # --- Bill reversal ---

    def test_reverse_bill_creates_reversal(self):
        bill = self._posted_bill()
        reversal = reverse_vendor_bill(bill, self.user, date(2025, 6, 30), "Test reversal")
        self.assertEqual(reversal.status, POSTED)
        self.assertIsNotNone(reversal.journal_entry)

    def test_reverse_bill_marks_original_reversed(self):
        bill = self._posted_bill()
        reverse_vendor_bill(bill, self.user, date(2025, 6, 30))
        bill.refresh_from_db()
        self.assertTrue(bill.is_reversed)

    def test_reverse_bill_net_je_is_zero(self):
        """Original JE + reversal JE totals cancel to zero on each account."""
        bill = self._posted_bill()
        reversal = reverse_vendor_bill(bill, self.user, date(2025, 6, 30))
        from django.db.models import Sum
        orig = bill.journal_entry.lines.aggregate(d=Sum("debit"), c=Sum("credit"))
        rev = reversal.journal_entry.lines.aggregate(d=Sum("debit"), c=Sum("credit"))
        self.assertEqual(orig["d"], rev["c"])
        self.assertEqual(orig["c"], rev["d"])

    def test_reverse_bill_raises_if_not_posted(self):
        bill = VendorBill.objects.create(
            project=self.project, contact=self.vendor,
            date=date(2025, 6, 1), currency=self.base,
            exchange_rate=Decimal("1"), created_by=self.user,
        )
        with self.assertRaises(ValueError):
            reverse_vendor_bill(bill, self.user, date(2025, 6, 30))

    def test_reverse_bill_raises_if_already_reversed(self):
        bill = self._posted_bill()
        reverse_vendor_bill(bill, self.user, date(2025, 6, 30))
        with self.assertRaises(ValueError):
            reverse_vendor_bill(bill, self.user, date(2025, 6, 30))

    # --- Invoice reversal ---

    def test_reverse_invoice(self):
        inv = self._posted_invoice()
        reversal = reverse_customer_invoice(inv, self.user, date(2025, 6, 30))
        self.assertEqual(reversal.status, POSTED)
        inv.refresh_from_db()
        self.assertTrue(inv.is_reversed)

    def test_reverse_invoice_je_cancels(self):
        inv = self._posted_invoice()
        reversal = reverse_customer_invoice(inv, self.user, date(2025, 6, 30))
        from django.db.models import Sum
        orig = inv.journal_entry.lines.aggregate(d=Sum("debit"), c=Sum("credit"))
        rev = reversal.journal_entry.lines.aggregate(d=Sum("debit"), c=Sum("credit"))
        self.assertEqual(orig["d"], rev["c"])
        self.assertEqual(orig["c"], rev["d"])

    # --- Payment reversal ---

    def test_reverse_payment(self):
        pay = self._posted_payment()
        reversal = reverse_payment(pay, self.user, date(2025, 6, 30))
        self.assertEqual(reversal.status, POSTED)
        pay.refresh_from_db()
        self.assertTrue(pay.is_reversed)

    # --- Receipt reversal ---

    def test_reverse_receipt(self):
        rec = self._posted_receipt()
        reversal = reverse_receipt(rec, self.user, date(2025, 6, 30))
        self.assertEqual(reversal.status, POSTED)
        rec.refresh_from_db()
        self.assertTrue(rec.is_reversed)


# ---------------------------------------------------------------------------
# 8. Partial payments & multi-payment settlement (invoice)
# ---------------------------------------------------------------------------

class PartialReceiptSettlementTests(TestCase):
    """Invoice settled in multiple receipts; balance decrements correctly."""

    def setUp(self):
        self.base = _make_currency("AFN")
        self.project = _make_project(self.base)
        self.user = _make_user()
        self.customer = _make_customer(self.project)
        self.revenue = _revenue_account(self.project)
        self.cashbox = _make_cashbox(self.project, "AFN Cash", self.base)

    def _posted_invoice(self, amount=Decimal("1000")):
        inv = CustomerInvoice.objects.create(
            project=self.project, contact=self.customer,
            date=date(2025, 6, 1), currency=self.base,
            exchange_rate=Decimal("1"), created_by=self.user,
        )
        CustomerInvoiceLine.objects.create(
            invoice=inv, account=self.revenue,
            quantity=Decimal("1"), unit_price=amount,
        )
        return post_customer_invoice(inv, self.user)

    def _post_receipt(self, invoice, amount):
        rec = Receipt.objects.create(
            project=self.project, contact=self.customer,
            date=date(2025, 6, 10), currency=self.base,
            exchange_rate=Decimal("1"), amount=amount,
            cashbox=self.cashbox, invoice=invoice,
            created_by=self.user,
        )
        return post_receipt(rec, self.user)

    def test_balance_decrements_after_first_partial_receipt(self):
        inv = self._posted_invoice(Decimal("1000"))
        self._post_receipt(inv, Decimal("400"))
        self.assertEqual(inv.balance_tc(), Decimal("600.00"))
        self.assertEqual(inv.received_tc(), Decimal("400.00"))

    def test_balance_zero_after_full_settlement(self):
        inv = self._posted_invoice(Decimal("500"))
        self._post_receipt(inv, Decimal("300"))
        self._post_receipt(inv, Decimal("200"))
        self.assertEqual(inv.balance_tc(), Decimal("0.00"))

    def test_multiple_receipts_each_je_balanced(self):
        from django.db.models import Sum
        inv = self._posted_invoice(Decimal("900"))
        r1 = self._post_receipt(inv, Decimal("300"))
        r2 = self._post_receipt(inv, Decimal("300"))
        for rec in [r1, r2]:
            agg = rec.journal_entry.lines.aggregate(d=Sum("debit"), c=Sum("credit"))
            self.assertEqual(agg["d"], agg["c"], f"JE not balanced for {rec.number}")

    def test_reversed_receipt_restores_balance(self):
        inv = self._posted_invoice(Decimal("1000"))
        rec = self._post_receipt(inv, Decimal("400"))
        self.assertEqual(inv.balance_tc(), Decimal("600.00"))
        reverse_receipt(rec, self.user, date(2025, 6, 20))
        # After reversal the receipt's contribution should be zero
        self.assertEqual(inv.balance_tc(), Decimal("1000.00"))

    def test_reversed_invoice_shows_zero_balance(self):
        inv = self._posted_invoice(Decimal("1000"))
        self._post_receipt(inv, Decimal("400"))
        reverse_customer_invoice(inv, self.user, date(2025, 6, 30))
        inv.refresh_from_db()
        self.assertEqual(inv.balance_tc(), Decimal("0.00"))


# ---------------------------------------------------------------------------
# 9. Partial payments & multi-payment settlement (bill)
# ---------------------------------------------------------------------------

class PartialPaymentSettlementTests(TestCase):
    """Bill settled in multiple payments; balance decrements correctly."""

    def setUp(self):
        self.base = _make_currency("AFN")
        self.project = _make_project(self.base)
        self.user = _make_user()
        self.vendor = _make_vendor(self.project)
        self.expense = _expense_account(self.project)
        self.cashbox = _make_cashbox(self.project, "AFN Cash", self.base)

    def _posted_bill(self, amount=Decimal("1000")):
        bill = VendorBill.objects.create(
            project=self.project, contact=self.vendor,
            date=date(2025, 6, 1), currency=self.base,
            exchange_rate=Decimal("1"), created_by=self.user,
        )
        VendorBillLine.objects.create(
            bill=bill, account=self.expense,
            quantity=Decimal("1"), unit_price=amount,
        )
        return post_vendor_bill(bill, self.user)

    def _post_payment(self, bill, amount):
        pay = Payment.objects.create(
            project=self.project, contact=self.vendor,
            date=date(2025, 6, 10), currency=self.base,
            exchange_rate=Decimal("1"), amount=amount,
            cashbox=self.cashbox, bill=bill,
            created_by=self.user,
        )
        return post_payment(pay, self.user)

    def test_balance_decrements_after_partial_payment(self):
        bill = self._posted_bill(Decimal("1000"))
        self._post_payment(bill, Decimal("600"))
        self.assertEqual(bill.balance_tc(), Decimal("400.00"))
        self.assertEqual(bill.paid_tc(), Decimal("600.00"))

    def test_balance_zero_after_full_settlement(self):
        bill = self._posted_bill(Decimal("800"))
        self._post_payment(bill, Decimal("500"))
        self._post_payment(bill, Decimal("300"))
        self.assertEqual(bill.balance_tc(), Decimal("0.00"))

    def test_reversed_payment_restores_balance(self):
        bill = self._posted_bill(Decimal("1000"))
        pay = self._post_payment(bill, Decimal("600"))
        self.assertEqual(bill.balance_tc(), Decimal("400.00"))
        reverse_payment(pay, self.user, date(2025, 6, 20))
        self.assertEqual(bill.balance_tc(), Decimal("1000.00"))

    def test_reversed_bill_shows_zero_balance(self):
        bill = self._posted_bill(Decimal("1000"))
        self._post_payment(bill, Decimal("400"))
        reverse_vendor_bill(bill, self.user, date(2025, 6, 30))
        bill.refresh_from_db()
        self.assertEqual(bill.balance_tc(), Decimal("0.00"))


# ---------------------------------------------------------------------------
# 10. Cross-currency settlement with FX gain/loss
# ---------------------------------------------------------------------------

class CrossCurrencySettlementTests(TestCase):
    """
    Invoice booked in USD at rate 70, receipt paid via USD cashbox at rate 75.
    Difference goes to FX Gain/Loss account; JE must still balance in BC.
    """

    def setUp(self):
        self.base = _make_currency("AFN")
        self.usd = _make_currency("USD")
        self.project = _make_project(self.base)
        self.user = _make_user()
        self.customer = _make_customer(self.project)
        self.vendor = _make_vendor(self.project)
        self.revenue = _revenue_account(self.project)
        self.expense = _expense_account(self.project)
        self.usd_cashbox = _make_cashbox(self.project, "USD Cash", self.usd)
        _seed_account(self.project, self.usd_cashbox.account, self.usd, Decimal("1000000"))
        self.afn_cashbox = _make_cashbox(self.project, "AFN Cash", self.base)

    def test_invoice_usd_receipt_usd_same_rate_no_fx_line(self):
        """Same rate — no FX gain/loss line needed."""
        inv = CustomerInvoice.objects.create(
            project=self.project, contact=self.customer,
            date=date(2025, 6, 1), currency=self.usd,
            exchange_rate=Decimal("70"), created_by=self.user,
        )
        CustomerInvoiceLine.objects.create(
            invoice=inv, account=self.revenue,
            quantity=Decimal("1"), unit_price=Decimal("100"),
        )
        post_customer_invoice(inv, self.user)

        rec = Receipt.objects.create(
            project=self.project, contact=self.customer,
            date=date(2025, 6, 10), currency=self.usd,
            exchange_rate=Decimal("70"), amount=Decimal("100"),
            cashbox=self.usd_cashbox, invoice=inv,
            created_by=self.user,
        )
        post_receipt(rec, self.user)
        from django.db.models import Sum
        agg = rec.journal_entry.lines.aggregate(d=Sum("debit"), c=Sum("credit"))
        self.assertEqual(agg["d"], agg["c"])
        self.assertEqual(inv.balance_tc(), Decimal("0.00"))

    def test_invoice_usd_receipt_usd_different_rate_fx_balance(self):
        """Receipt uses rate 75 vs invoice rate 70 — FX gain/loss line added."""
        inv = CustomerInvoice.objects.create(
            project=self.project, contact=self.customer,
            date=date(2025, 6, 1), currency=self.usd,
            exchange_rate=Decimal("70"), created_by=self.user,
        )
        CustomerInvoiceLine.objects.create(
            invoice=inv, account=self.revenue,
            quantity=Decimal("1"), unit_price=Decimal("100"),
        )
        post_customer_invoice(inv, self.user)

        rec = Receipt.objects.create(
            project=self.project, contact=self.customer,
            date=date(2025, 6, 15), currency=self.usd,
            exchange_rate=Decimal("75"), amount=Decimal("100"),
            cashbox=self.usd_cashbox, invoice=inv,
            created_by=self.user,
        )
        post_receipt(rec, self.user)
        from django.db.models import Sum
        agg = rec.journal_entry.lines.aggregate(d=Sum("debit"), c=Sum("credit"))
        self.assertEqual(agg["d"], agg["c"])
        # balance_tc uses invoice rate; invoice is fully settled in TC
        self.assertEqual(inv.balance_tc(), Decimal("0.00"))

    def test_bill_usd_payment_usd_different_rate_je_balanced(self):
        """Bill at rate 70, payment at rate 72 — JE balanced via FX line."""
        bill = VendorBill.objects.create(
            project=self.project, contact=self.vendor,
            date=date(2025, 6, 1), currency=self.usd,
            exchange_rate=Decimal("70"), created_by=self.user,
        )
        VendorBillLine.objects.create(
            bill=bill, account=self.expense,
            quantity=Decimal("1"), unit_price=Decimal("200"),
        )
        post_vendor_bill(bill, self.user)

        pay = Payment.objects.create(
            project=self.project, contact=self.vendor,
            date=date(2025, 6, 15), currency=self.usd,
            exchange_rate=Decimal("72"), amount=Decimal("200"),
            cashbox=self.usd_cashbox, bill=bill,
            created_by=self.user,
        )
        post_payment(pay, self.user)
        from django.db.models import Sum
        agg = pay.journal_entry.lines.aggregate(d=Sum("debit"), c=Sum("credit"))
        self.assertEqual(agg["d"], agg["c"])
        self.assertEqual(bill.balance_tc(), Decimal("0.00"))

    def test_partial_cross_currency_receipt_balance_correct(self):
        """Partial receipt in USD leaves correct TC balance on invoice."""
        inv = CustomerInvoice.objects.create(
            project=self.project, contact=self.customer,
            date=date(2025, 6, 1), currency=self.usd,
            exchange_rate=Decimal("70"), created_by=self.user,
        )
        CustomerInvoiceLine.objects.create(
            invoice=inv, account=self.revenue,
            quantity=Decimal("1"), unit_price=Decimal("300"),
        )
        post_customer_invoice(inv, self.user)

        # pay 100 out of 300
        rec = Receipt.objects.create(
            project=self.project, contact=self.customer,
            date=date(2025, 6, 10), currency=self.usd,
            exchange_rate=Decimal("70"), amount=Decimal("100"),
            cashbox=self.usd_cashbox, invoice=inv,
            created_by=self.user,
        )
        post_receipt(rec, self.user)
        self.assertEqual(inv.received_tc(), Decimal("100.00"))
        self.assertEqual(inv.balance_tc(), Decimal("200.00"))

    def test_reversal_of_cross_currency_receipt_restores_balance(self):
        """Reversing a USD receipt restores the full TC outstanding."""
        inv = CustomerInvoice.objects.create(
            project=self.project, contact=self.customer,
            date=date(2025, 6, 1), currency=self.usd,
            exchange_rate=Decimal("70"), created_by=self.user,
        )
        CustomerInvoiceLine.objects.create(
            invoice=inv, account=self.revenue,
            quantity=Decimal("1"), unit_price=Decimal("200"),
        )
        post_customer_invoice(inv, self.user)

        rec = Receipt.objects.create(
            project=self.project, contact=self.customer,
            date=date(2025, 6, 10), currency=self.usd,
            exchange_rate=Decimal("73"), amount=Decimal("200"),
            cashbox=self.usd_cashbox, invoice=inv,
            created_by=self.user,
        )
        post_receipt(rec, self.user)
        self.assertEqual(inv.balance_tc(), Decimal("0.00"))

        reverse_receipt(rec, self.user, date(2025, 6, 20))
        # After reversing, the original receipt should count but the reversal cancels it
        self.assertEqual(inv.balance_tc(), Decimal("200.00"))

    def test_fx_gain_loss_account_created_when_needed(self):
        """_fx_balance creates FX accounts if they don't exist yet."""
        from coa.services import get_or_create_fx_accounts
        gain_acc, loss_acc = get_or_create_fx_accounts(self.project)
        self.assertIsNotNone(gain_acc)
        self.assertIsNotNone(loss_acc)


# ---------------------------------------------------------------------------
# 11. Cross-currency cashbox: bill in AFN paid from USD cashbox
# ---------------------------------------------------------------------------

class BillAFNPayFromUSDCashboxTests(TestCase):
    """
    Bill is recorded in AFN (base currency).
    Vendor is paid from a USD cashbox at a specified AFN/USD rate.
    The TC balance on the bill should reflect the AFN-equivalent of the
    USD payment; the JE must balance.
    """

    def setUp(self):
        self.base = _make_currency("AFN")
        self.usd  = _make_currency("USD")
        self.project = _make_project(self.base)
        self.user = _make_user()
        self.vendor = _make_vendor(self.project)
        self.expense = _expense_account(self.project)
        self.usd_cashbox = _make_cashbox(self.project, "USD Cash", self.usd)
        _seed_account(self.project, self.usd_cashbox.account, self.usd, Decimal("1000000"))

    def _posted_afn_bill(self, amount_afn=Decimal("7500")):
        bill = VendorBill.objects.create(
            project=self.project, contact=self.vendor,
            date=date(2025, 6, 1), currency=self.base,
            exchange_rate=Decimal("1"), created_by=self.user,
        )
        VendorBillLine.objects.create(
            bill=bill, account=self.expense,
            quantity=Decimal("1"), unit_price=amount_afn,
        )
        return post_vendor_bill(bill, self.user)

    def test_full_settlement_from_usd_cashbox(self):
        """Pay 100 USD @ 75 AFN/USD fully settles a 7500 AFN bill."""
        bill = self._posted_afn_bill(Decimal("7500"))
        pay = Payment.objects.create(
            project=self.project, contact=self.vendor,
            date=date(2025, 6, 10), currency=self.usd,
            exchange_rate=Decimal("75"),  # 1 USD = 75 AFN
            amount=Decimal("100"),         # 100 USD × 75 = 7500 AFN
            cashbox=self.usd_cashbox, bill=bill,
            created_by=self.user,
        )
        post_payment(pay, self.user)
        self.assertEqual(bill.balance_tc(), Decimal("0.00"))
        self.assertEqual(bill.paid_tc(), Decimal("7500.00"))

    def test_partial_payment_from_usd_cashbox(self):
        """Pay 50 USD @ 75 = 3750 AFN; leaves 3750 AFN remaining on a 7500 AFN bill."""
        bill = self._posted_afn_bill(Decimal("7500"))
        pay = Payment.objects.create(
            project=self.project, contact=self.vendor,
            date=date(2025, 6, 10), currency=self.usd,
            exchange_rate=Decimal("75"),
            amount=Decimal("50"),
            cashbox=self.usd_cashbox, bill=bill,
            created_by=self.user,
        )
        post_payment(pay, self.user)
        self.assertEqual(bill.paid_tc(), Decimal("3750.00"))
        self.assertEqual(bill.balance_tc(), Decimal("3750.00"))

    def test_usd_payment_je_balanced(self):
        """JE for a USD payment against an AFN bill must balance in BC (AFN)."""
        from django.db.models import Sum
        bill = self._posted_afn_bill(Decimal("9000"))
        pay = Payment.objects.create(
            project=self.project, contact=self.vendor,
            date=date(2025, 6, 10), currency=self.usd,
            exchange_rate=Decimal("90"),  # 1 USD = 90 AFN
            amount=Decimal("100"),         # 100 × 90 = 9000 AFN
            cashbox=self.usd_cashbox, bill=bill,
            created_by=self.user,
        )
        post_payment(pay, self.user)
        agg = pay.journal_entry.lines.aggregate(d=Sum("debit"), c=Sum("credit"))
        self.assertEqual(agg["d"], agg["c"])

    def test_reversal_of_usd_payment_restores_afn_balance(self):
        """Reversing the USD payment restores the full AFN balance on the bill."""
        bill = self._posted_afn_bill(Decimal("7500"))
        pay = Payment.objects.create(
            project=self.project, contact=self.vendor,
            date=date(2025, 6, 10), currency=self.usd,
            exchange_rate=Decimal("75"),
            amount=Decimal("100"),
            cashbox=self.usd_cashbox, bill=bill,
            created_by=self.user,
        )
        post_payment(pay, self.user)
        self.assertEqual(bill.balance_tc(), Decimal("0.00"))
        reverse_payment(pay, self.user, date(2025, 6, 20))
        self.assertEqual(bill.balance_tc(), Decimal("7500.00"))


# ---------------------------------------------------------------------------
# 12. Cross-currency receipt: invoice in USD, receipt in AFN (base currency)
# ---------------------------------------------------------------------------

class InvoiceUSDReceiptAFNTests(TestCase):
    """
    Invoice is in USD.  Customer pays in AFN (base currency) providing
    the AFN-per-USD exchange rate so the USD outstanding decrements correctly.
    """

    def setUp(self):
        self.base = _make_currency("AFN")
        self.usd  = _make_currency("USD")
        self.project = _make_project(self.base)
        self.user = _make_user()
        self.customer = _make_customer(self.project)
        self.revenue = _revenue_account(self.project)
        self.afn_cashbox = _make_cashbox(self.project, "AFN Cash", self.base)

    def _posted_usd_invoice(self, amount_usd=Decimal("100"), rate=Decimal("75")):
        inv = CustomerInvoice.objects.create(
            project=self.project, contact=self.customer,
            date=date(2025, 6, 1), currency=self.usd,
            exchange_rate=rate, created_by=self.user,
        )
        CustomerInvoiceLine.objects.create(
            invoice=inv, account=self.revenue,
            quantity=Decimal("1"), unit_price=amount_usd,
        )
        return post_customer_invoice(inv, self.user)

    def test_full_settlement_in_afn(self):
        """Receipt of 7500 AFN @ rate 75 fully settles a 100 USD invoice booked at 75."""
        inv = self._posted_usd_invoice(Decimal("100"), Decimal("75"))
        rec = Receipt.objects.create(
            project=self.project, contact=self.customer,
            date=date(2025, 6, 10), currency=self.base,  # AFN
            exchange_rate=Decimal("75"),                  # today's rate: 1 USD = 75 AFN
            amount=Decimal("7500"),                       # 7500 AFN / 75 = 100 USD cleared
            cashbox=self.afn_cashbox, invoice=inv,
            created_by=self.user,
        )
        post_receipt(rec, self.user)
        # received_tc = 7500 AFN / 75 = 100 USD
        self.assertEqual(inv.received_tc(), Decimal("100.00"))
        self.assertEqual(inv.balance_tc(), Decimal("0.00"))

    def test_partial_settlement_in_afn(self):
        """Receipt of 3000 AFN partially settles a 100 USD invoice at rate 75."""
        inv = self._posted_usd_invoice(Decimal("100"), Decimal("75"))
        rec = Receipt.objects.create(
            project=self.project, contact=self.customer,
            date=date(2025, 6, 10), currency=self.base,
            exchange_rate=Decimal("75"),  # today's rate: 1 USD = 75 AFN
            amount=Decimal("3000"),       # 3000 / 75 = 40 USD cleared
            cashbox=self.afn_cashbox, invoice=inv,
            created_by=self.user,
        )
        post_receipt(rec, self.user)
        self.assertEqual(inv.received_tc(), Decimal("40.00"))
        self.assertEqual(inv.balance_tc(), Decimal("60.00"))

    def test_afn_receipt_je_balanced(self):
        """JE for an AFN receipt against a USD invoice must balance in BC (AFN)."""
        from django.db.models import Sum
        inv = self._posted_usd_invoice(Decimal("100"), Decimal("75"))
        rec = Receipt.objects.create(
            project=self.project, contact=self.customer,
            date=date(2025, 6, 10), currency=self.base,
            exchange_rate=Decimal("75"),  # today's rate: 1 USD = 75 AFN
            amount=Decimal("7500"),
            cashbox=self.afn_cashbox, invoice=inv,
            created_by=self.user,
        )
        post_receipt(rec, self.user)
        agg = rec.journal_entry.lines.aggregate(d=Sum("debit"), c=Sum("credit"))
        self.assertEqual(agg["d"], agg["c"])

    def test_afn_receipt_reversal_restores_usd_balance(self):
        """Reversing an AFN receipt restores the full USD outstanding."""
        inv = self._posted_usd_invoice(Decimal("100"), Decimal("75"))
        rec = Receipt.objects.create(
            project=self.project, contact=self.customer,
            date=date(2025, 6, 10), currency=self.base,
            exchange_rate=Decimal("75"),  # today's rate: 1 USD = 75 AFN
            amount=Decimal("7500"),
            cashbox=self.afn_cashbox, invoice=inv,
            created_by=self.user,
        )
        post_receipt(rec, self.user)
        self.assertEqual(inv.balance_tc(), Decimal("0.00"))
        reverse_receipt(rec, self.user, date(2025, 6, 20))
        self.assertEqual(inv.balance_tc(), Decimal("100.00"))

    def test_multi_currency_receipts_settle_usd_invoice(self):
        """Two receipts — one USD, one AFN — together settle a 200 USD invoice."""
        usd_cashbox = _make_cashbox(self.project, "USD Cash", self.usd)
        _seed_account(self.project, usd_cashbox.account, self.usd, Decimal("1000000"))

        inv = self._posted_usd_invoice(Decimal("200"), Decimal("75"))

        # First: 7500 AFN / 75 = 100 USD
        rec1 = Receipt.objects.create(
            project=self.project, contact=self.customer,
            date=date(2025, 6, 10), currency=self.base,
            exchange_rate=Decimal("75"), amount=Decimal("7500"),  # today's rate
            cashbox=self.afn_cashbox, invoice=inv,
            created_by=self.user,
        )
        post_receipt(rec1, self.user)

        # Second: 100 USD (same currency as invoice)
        rec2 = Receipt.objects.create(
            project=self.project, contact=self.customer,
            date=date(2025, 6, 15), currency=self.usd,
            exchange_rate=Decimal("75"), amount=Decimal("100"),
            cashbox=usd_cashbox, invoice=inv,
            created_by=self.user,
        )
        post_receipt(rec2, self.user)

        self.assertEqual(inv.balance_tc(), Decimal("0.00"))
