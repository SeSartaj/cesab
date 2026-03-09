"""
Transaction service tests.

Scenarios covered
─────────────────
VendorPaymentFXTests
  1. Record a $100 USD bill at 60 AFN/USD.
  2. Pay $60 from a USD cashbox — no exchange rate required from the caller;
     the service auto-uses the original booking rate.
  3. Pay the remaining $40 from an AFN cashbox at 62 AFN/USD — an FX loss of
     80 AFN is generated because the rate moved against us.
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
import transactions.services as svc


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_currency(code, name, symbol=""):
    c, _ = Currency.objects.get_or_create(
        code=code, defaults={"name": name, "symbol": symbol, "is_active": True}
    )
    return c


def _fund_account(user, project, account, currency, amount_bc, amount_tc):
    """
    Inject money into an account by creating a bare JournalLine (debit).
    This simulates a capital injection without going through the full
    capital-contribution flow (which would require partners etc.).
    """
    je = JournalEntry.objects.create(
        project=project,
        date=date(2026, 1, 1),
        description=f"Seed funds – {account.name}",
        transaction_type="manual",
        created_by=user,
    )
    JournalLine.objects.create(
        journal_entry=je,
        account=account,
        debit=amount_bc,
        credit=Decimal("0"),
        transaction_currency=currency,
        exchange_rate=(amount_bc / amount_tc).quantize(Decimal("0.000001")) if amount_tc else Decimal("1"),
        debit_tc=amount_tc,
        credit_tc=Decimal("0"),
    )
    return je


def _make_cashbox(project, code, name, currency):
    account = Account.objects.create(
        project=project,
        code=code,
        name=name,
        account_type="asset",
        parent=Account.objects.filter(project=project, code="1100").first(),
    )
    return Cashbox.objects.create(
        project=project, name=name, account=account, currency=currency
    )


class VendorPaymentFXTests(TestCase):
    """
    Full lifecycle: bill → same-currency cashbox payment → cross-currency payment.

    Setup
    ─────
    Base currency : AFN
    Foreign       : USD
    Vendor        : "Cement Co"
    Bill          : 100 USD @ 60 AFN/USD  →  6 000 AFN payable
    Payment 1     : 60 USD from USD cashbox  (no conversion; rate auto-detected)
    Payment 2     : 40 USD from AFN cashbox  @ 62 AFN/USD  (FX loss 80 AFN)
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("tester", password="x")

        cls.afn = _make_currency("AFN", "Afghan Afghani", "؋")
        cls.usd = _make_currency("USD", "US Dollar", "$")

        cls.project = Project.objects.create(name="Test Project", base_currency=cls.afn)
        create_standard_coa(cls.project)

        # --- Expense account (reuse 5100 Direct Costs) ---
        cls.expense_acc = Account.objects.get(project=cls.project, code="5100")

        # --- Vendor (create accounts manually to avoid import complexity) ---
        from coa.services import create_vendor_accounts
        from vendors.services import create_vendor as svc_create_vendor
        cls.vendor = svc_create_vendor(project=cls.project, name="Cement Co")

        # --- Cashboxes ---
        cls.usd_cashbox = _make_cashbox(cls.project, "1181", "USD Cash", cls.usd)
        cls.afn_cashbox = _make_cashbox(cls.project, "1182", "AFN Cash", cls.afn)

        # Fund USD cashbox: 200 USD @ 60 → 12 000 AFN
        _fund_account(cls.user, cls.project,
                      cls.usd_cashbox.account, cls.usd,
                      amount_bc=Decimal("12000"), amount_tc=Decimal("200"))

        # Fund AFN cashbox: 10 000 AFN
        _fund_account(cls.user, cls.project,
                      cls.afn_cashbox.account, cls.afn,
                      amount_bc=Decimal("10000"), amount_tc=Decimal("10000"))

    # ------------------------------------------------------------------
    # Step 1: Record the bill
    # ------------------------------------------------------------------

    def _record_bill(self):
        """Helper: $100 USD bill at 60 AFN/USD → 6 000 AFN payable."""
        return svc.vendor_bill(
            project=self.project, user=self.user,
            date=date(2026, 2, 1),
            vendor=self.vendor,
            expense_account=self.expense_acc,
            amount=100,
            description="Cement bill",
            currency=self.usd,
            exchange_rate=60,
        )

    def test_bill_creates_correct_payable(self):
        """Bill should create a 6 000 AFN / 100 USD liability."""
        je = self._record_bill()

        lines = list(je.lines.all())
        self.assertEqual(len(lines), 2)

        payable_line = next(l for l in lines if l.account == self.vendor.payable_account)
        self.assertEqual(payable_line.credit, Decimal("6000.00"))
        self.assertEqual(payable_line.credit_tc, Decimal("100.00"))
        self.assertEqual(payable_line.transaction_currency, self.usd)

        # Payable balance: 6 000 AFN
        self.assertEqual(self.vendor.balance_payable(), Decimal("6000.00"))

    # ------------------------------------------------------------------
    # Step 2: Pay $60 from USD cashbox — no exchange rate required
    # ------------------------------------------------------------------

    def test_payment_from_usd_cashbox_no_fx(self):
        """
        Paying $60 from a USD cashbox against a USD payable should:
        - produce exactly 2 lines (payable + cashbox); no FX line
        - debit payable 60 USD @ bill_rate (60) = 3 600 AFN
        - credit USD cashbox 60 USD @ 60 = 3 600 AFN  (TC in USD)
        - leave 40 USD / 2 400 AFN still outstanding
        - not require the caller to supply an exchange rate (exchange_rate=1 works)
        """
        self._record_bill()

        je = svc.vendor_payment_against_bill(
            project=self.project, user=self.user,
            date=date(2026, 2, 15),
            vendor=self.vendor,
            amount=60,
            cashbox=self.usd_cashbox,
            description="Pay $60 USD cashbox",
            currency=self.usd,
            exchange_rate=1,          # caller does NOT need to supply a rate
        )

        lines = list(je.lines.all())
        self.assertEqual(len(lines), 2, "No FX line expected when paying same-currency cashbox")

        payable_line = next(l for l in lines if l.account == self.vendor.payable_account)
        cashbox_line = next(l for l in lines if l.account == self.usd_cashbox.account)

        # Payable debited at original booking rate
        self.assertEqual(payable_line.debit,    Decimal("3600.00"))
        self.assertEqual(payable_line.debit_tc, Decimal("60.00"))
        self.assertEqual(payable_line.transaction_currency, self.usd)

        # USD cashbox credited in USD
        self.assertEqual(cashbox_line.credit,    Decimal("3600.00"))
        self.assertEqual(cashbox_line.credit_tc, Decimal("60.00"))
        self.assertEqual(cashbox_line.transaction_currency, self.usd)

        # 40 USD / 2 400 AFN still outstanding
        self.assertEqual(self.vendor.balance_payable(), Decimal("2400.00"))
        # USD cashbox reduced by 60 USD
        self.assertEqual(self.usd_cashbox.balance_in_currency(), Decimal("140.00"))

    # ------------------------------------------------------------------
    # Step 3: Pay remaining $40 from AFN cashbox at 62 AFN/USD → FX loss
    # ------------------------------------------------------------------

    def test_payment_from_afn_cashbox_with_fx_loss(self):
        """
        Paying $40 at 62 AFN/USD from an AFN cashbox, when the bill was booked at 60:
        - payable debited at original rate:  40 × 60 = 2 400 AFN
        - AFN cashbox credited at today's rate: 40 × 62 = 2 480 AFN
        - FX Loss of 80 AFN (we're paying more AFN than booked)
        - 3 lines total; payable fully cleared
        """
        self._record_bill()

        # First clear $60 via USD cashbox (same as previous test)
        svc.vendor_payment_against_bill(
            project=self.project, user=self.user,
            date=date(2026, 2, 15),
            vendor=self.vendor,
            amount=60, cashbox=self.usd_cashbox,
            currency=self.usd, exchange_rate=1,
        )

        # Now pay the remaining $40 from the AFN cashbox at 62
        je = svc.vendor_payment_against_bill(
            project=self.project, user=self.user,
            date=date(2026, 2, 28),
            vendor=self.vendor,
            amount=40,
            cashbox=self.afn_cashbox,
            description="Pay $40 from AFN cashbox at 62",
            currency=self.usd,
            exchange_rate=62,
        )

        lines = list(je.lines.all())
        self.assertEqual(len(lines), 3, "Expected payable + FX Loss + AFN cashbox lines")

        payable_line = next(l for l in lines if l.account == self.vendor.payable_account)
        cashbox_line = next(l for l in lines if l.account == self.afn_cashbox.account)
        fx_lines     = [l for l in lines
                        if l.account not in (self.vendor.payable_account, self.afn_cashbox.account)]
        self.assertEqual(len(fx_lines), 1)
        fx_line = fx_lines[0]

        # Payable debited at original booking rate (60)
        self.assertEqual(payable_line.debit,    Decimal("2400.00"))
        self.assertEqual(payable_line.debit_tc, Decimal("40.00"))
        self.assertEqual(payable_line.transaction_currency, self.usd)

        # FX Loss = (40 × 62) − (40 × 60) = 80 AFN
        self.assertEqual(fx_line.debit,    Decimal("80.00"))
        self.assertEqual(fx_line.debit_tc, Decimal("80.00"))
        self.assertEqual(fx_line.transaction_currency, self.afn)

        # AFN cashbox credited at today's rate
        self.assertEqual(cashbox_line.credit,    Decimal("2480.00"))
        self.assertEqual(cashbox_line.credit_tc, Decimal("2480.00"))
        self.assertEqual(cashbox_line.transaction_currency, self.afn)

        # Payable fully settled
        self.assertEqual(self.vendor.balance_payable(), Decimal("0.00"))
        # AFN cashbox reduced by 2 480
        self.assertEqual(self.afn_cashbox.balance(), Decimal("7520.00"))

    # ------------------------------------------------------------------
    # Scenario C: AFN bill, USD cashbox (spot conversion, no FX gain/loss)
    # ------------------------------------------------------------------

    def test_payment_from_usd_cashbox_for_afn_bill(self):
        """
        AFN bill (base currency) paid from a USD cashbox at 63 AFN/USD.

        10 000 / 63 = 158.730158…  → TC rounded to 158.73 USD
        158.73 × 63 = 9 999.99  ≠  10 000  — the round-trip drifts by 0.01.
        Despite the rounding, BC must stay exactly 10 000 AFN (no drift).

        Entry expected:
          Dr. Payable   10 000.00 AFN   [TC: 10 000.00 AFN]
          Cr. USD Cash  10 000.00 AFN   [TC:    158.73 USD @ 63]

        No FX line — the payable is already in base currency.
        """
        # Record a plain AFN bill
        svc.vendor_bill(
            project=self.project, user=self.user,
            date=date(2026, 3, 1),
            vendor=self.vendor,
            expense_account=self.expense_acc,
            amount=10000,
            description="AFN cement bill",
            currency=self.afn,
            exchange_rate=1,
        )
        payable_before = self.vendor.balance_payable()
        self.assertEqual(payable_before, Decimal("10000.00"))

        # Pay from USD cashbox at 63 AFN/USD
        je = svc.vendor_payment_against_bill(
            project=self.project, user=self.user,
            date=date(2026, 3, 15),
            vendor=self.vendor,
            amount=10000,
            cashbox=self.usd_cashbox,
            description="Pay AFN bill from USD cashbox",
            currency=self.afn,
            exchange_rate=63,
        )

        lines = list(je.lines.all())
        self.assertEqual(len(lines), 2, "No FX line expected — bill was in base currency")

        payable_line = next(l for l in lines if l.account == self.vendor.payable_account)
        cashbox_line = next(l for l in lines if l.account == self.usd_cashbox.account)

        # Payable debited in AFN — exact amount, no rounding drift
        self.assertEqual(payable_line.debit,    Decimal("10000.00"))
        self.assertEqual(payable_line.debit_tc, Decimal("10000.00"))
        self.assertEqual(payable_line.transaction_currency, self.afn)

        # USD cashbox: TC = round(10000/63, 2) = 158.73 USD, BC pinned to 10 000
        self.assertEqual(cashbox_line.credit_tc, Decimal("158.73"))
        self.assertEqual(cashbox_line.credit,    Decimal("10000.00"))
        self.assertEqual(cashbox_line.transaction_currency, self.usd)

        # Entry must balance
        self.assertEqual(je.total_debit(), je.total_credit())

        # Payable fully cleared
        self.assertEqual(self.vendor.balance_payable(), Decimal("0.00"))

    def test_payment_from_afn_cashbox_with_fx_gain(self):
        """
        Paying $100 at 58 AFN/USD when booked at 60 → FX Gain of 200 AFN.
        """
        self._record_bill()

        je = svc.vendor_payment_against_bill(
            project=self.project, user=self.user,
            date=date(2026, 2, 28),
            vendor=self.vendor,
            amount=100,
            cashbox=self.afn_cashbox,
            currency=self.usd,
            exchange_rate=58,
        )

        lines = list(je.lines.all())
        self.assertEqual(len(lines), 3)

        payable_line = next(l for l in lines if l.account == self.vendor.payable_account)
        cashbox_line = next(l for l in lines if l.account == self.afn_cashbox.account)
        fx_lines     = [l for l in lines
                        if l.account not in (self.vendor.payable_account, self.afn_cashbox.account)]
        fx_line = fx_lines[0]

        # Payable cleared at booking rate
        self.assertEqual(payable_line.debit,    Decimal("6000.00"))
        # Cashbox only gives 5 800 AFN
        self.assertEqual(cashbox_line.credit,   Decimal("5800.00"))
        # FX Gain = 6 000 − 5 800 = 200 (credit)
        self.assertEqual(fx_line.credit,    Decimal("200.00"))
        self.assertEqual(fx_line.credit_tc, Decimal("200.00"))

        self.assertEqual(self.vendor.balance_payable(), Decimal("0.00"))
