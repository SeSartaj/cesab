"""
Document services — all business logic for posting and reversing documents.

Each service validates state, creates a JournalEntry, and marks the
document as POSTED.  Reversal creates a mirror document and a reversal JE.

Multi-currency:
  - document.currency     = transaction currency (TC)
  - document.exchange_rate = base-currency units per 1 TC unit
  - Journal lines store both TC amounts (debit_tc / credit_tc) and BC amounts
    (debit / credit) so reports can aggregate either way.

FX on Payment / Receipt:
  When the cashbox currency differs from the document currency, an FX diff
  line is added to keep the JE balanced (same logic as transactions/services.py).
"""
from decimal import Decimal
from django.db import transaction as db_transaction
from django.utils import timezone

from journal.models import JournalEntry, JournalLine
from .models import DRAFT, POSTED, VendorBill, CustomerInvoice, Payment, Receipt


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _create_je(project, user, date, description, transaction_type):
    return JournalEntry.objects.create(
        project=project,
        date=date,
        description=description,
        transaction_type=transaction_type,
        created_by=user,
    )


def _add_line(je, account, debit=0, credit=0, currency=None, exchange_rate=1,
              debit_bc=None, credit_bc=None):
    if currency is None:
        currency = je.project.base_currency
    rate = Decimal(str(exchange_rate))
    d = Decimal(str(debit))
    c = Decimal(str(credit))
    JournalLine.objects.create(
        journal_entry=je,
        account=account,
        debit=Decimal(str(debit_bc)) if debit_bc is not None else (d * rate if rate != 1 else d),
        credit=Decimal(str(credit_bc)) if credit_bc is not None else (c * rate if rate != 1 else c),
        transaction_currency=currency,
        exchange_rate=rate,
        debit_tc=d,
        credit_tc=c,
    )


def _check_draft(document):
    if document.status != DRAFT:
        raise ValueError(
            f"{document.__class__.__name__} {document} is already posted and cannot be modified."
        )


def _check_posted(document):
    if document.status != POSTED:
        raise ValueError(
            f"{document.__class__.__name__} {document} must be posted before it can be reversed."
        )


def _check_not_reversed(document):
    if document.is_reversed:
        raise ValueError(f"{document.__class__.__name__} {document} has already been reversed.")


def _fx_balance(je, project):
    """Add an FX Gain/Loss line if the JE is not balanced, return the adjusted je."""
    from django.db.models import Sum
    from coa.services import get_or_create_fx_accounts
    totals = je.lines.aggregate(d=Sum("debit"), c=Sum("credit"))
    diff = (totals["d"] or Decimal("0")) - (totals["c"] or Decimal("0"))
    if diff == Decimal("0"):
        return
    gain_acc, loss_acc = get_or_create_fx_accounts(project)
    if diff > 0:
        _add_line(je, gain_acc, credit=diff, currency=project.base_currency, exchange_rate=1)
    else:
        _add_line(je, loss_acc, debit=-diff, currency=project.base_currency, exchange_rate=1)


def _assert_balanced(je):
    """Raise AssertionError if the JE does not balance. Called as a final safety check."""
    from django.db.models import Sum
    totals = je.lines.aggregate(d=Sum("debit"), c=Sum("credit"))
    d = totals["d"] or Decimal("0")
    c = totals["c"] or Decimal("0")
    if d != c:
        raise AssertionError(
            f"{je} is unbalanced — debit {d:,.2f} ≠ credit {c:,.2f}. "
            "This is a programming error; the transaction has been rolled back."
        )


# ---------------------------------------------------------------------------
# Vendor Bill
# ---------------------------------------------------------------------------

@db_transaction.atomic
def post_vendor_bill(bill: VendorBill, user) -> VendorBill:
    """
    Post a vendor bill.  Creates journal entry:

      For each line:
        Dr. line.account (expense)      line.subtotal (TC) × rate
        Dr. tax.account  (if tax)       line.tax_amount (TC) × rate
      Cr. contact.payable_account       bill.total_amount (TC) × rate
    """
    _check_draft(bill)
    if not bill.lines.exists():
        raise ValueError("Cannot post a bill with no lines.")
    if not bill.contact.payable_account:
        raise ValueError(
            f"Contact '{bill.contact}' has no payable account configured."
        )

    rate = bill.exchange_rate
    currency = bill.currency
    project = bill.project

    je = _create_je(
        project, user, bill.date,
        f"Vendor bill {bill.number} — {bill.contact.name}",
        "vendor_bill",
    )

    total_bc = Decimal("0")
    for line in bill.lines.all():
        sub_tc = line.subtotal()
        sub_bc = (sub_tc * rate).quantize(Decimal("0.01"))
        _add_line(je, line.account, debit=sub_tc, currency=currency,
                  exchange_rate=rate, debit_bc=sub_bc)
        total_bc += sub_bc

        if line.tax:
            tax_tc = line.tax_amount()
            tax_bc = (tax_tc * rate).quantize(Decimal("0.01"))
            _add_line(je, line.tax.account, debit=tax_tc, currency=currency,
                      exchange_rate=rate, debit_bc=tax_bc)
            total_bc += tax_bc

    _add_line(je, bill.contact.payable_account,
              credit=bill.total_amount(), currency=currency,
              exchange_rate=rate, credit_bc=total_bc)

    _assert_balanced(je)
    bill.journal_entry = je
    bill.status = POSTED
    bill.save(update_fields=["journal_entry", "status"])
    return bill


# ---------------------------------------------------------------------------
# Customer Invoice
# ---------------------------------------------------------------------------

@db_transaction.atomic
def post_customer_invoice(invoice: CustomerInvoice, user) -> CustomerInvoice:
    """
    Post a customer invoice.  Creates journal entry:

      Dr. contact.receivable_account    invoice.total_amount (TC) × rate
      For each line:
        Cr. line.account (revenue)      line.subtotal (TC) × rate
        Cr. tax.account  (if tax)       line.tax_amount (TC) × rate
    """
    _check_draft(invoice)
    if not invoice.lines.exists():
        raise ValueError("Cannot post an invoice with no lines.")
    if not invoice.contact.receivable_account:
        raise ValueError(
            f"Contact '{invoice.contact}' has no receivable account configured."
        )

    rate = invoice.exchange_rate
    currency = invoice.currency
    project = invoice.project

    je = _create_je(
        project, user, invoice.date,
        f"Customer invoice {invoice.number} — {invoice.contact.name}",
        "project_income",
    )

    total_bc = Decimal("0")
    for line in invoice.lines.all():
        sub_tc = line.subtotal()
        sub_bc = (sub_tc * rate).quantize(Decimal("0.01"))
        _add_line(je, line.account, credit=sub_tc, currency=currency,
                  exchange_rate=rate, credit_bc=sub_bc)
        total_bc += sub_bc

        if line.tax:
            tax_tc = line.tax_amount()
            tax_bc = (tax_tc * rate).quantize(Decimal("0.01"))
            _add_line(je, line.tax.account, credit=tax_tc, currency=currency,
                      exchange_rate=rate, credit_bc=tax_bc)
            total_bc += tax_bc

    _add_line(je, invoice.contact.receivable_account,
              debit=invoice.total_amount(), currency=currency,
              exchange_rate=rate, debit_bc=total_bc)

    _assert_balanced(je)
    invoice.journal_entry = je
    invoice.status = POSTED
    invoice.save(update_fields=["journal_entry", "status"])
    return invoice


# ---------------------------------------------------------------------------
# Payment (vendor → we pay)
# ---------------------------------------------------------------------------

@db_transaction.atomic
def post_payment(payment: Payment, user) -> Payment:
    """
    Post a payment to a vendor.  Creates journal entry:

      Dr. contact.payable_account    amount_tc × booking_rate  (BC)
      [Dr. FX Loss / Cr. FX Gain]   when today's rate ≠ booking rate
      Cr. cashbox.account            amount leaving cashbox  (BC)

    FX gain/loss arises when the payment currency equals the bill's foreign
    currency and the exchange rate has moved since the bill was recorded.
    BC booking rate comes from payment.bill.exchange_rate when linked.
    """
    _check_draft(payment)
    if not payment.contact.payable_account:
        raise ValueError(
            f"Contact '{payment.contact}' has no payable account configured."
        )

    project = payment.project
    base = project.base_currency
    pay_currency = payment.currency
    amount_tc = payment.amount
    pay_rate = payment.exchange_rate  # BC per 1 payment-currency unit (today's rate)
    cashbox = payment.cashbox
    cb_currency = cashbox.currency

    # Booking rate: BC per 1 bill-currency unit at invoice time.
    # Used to correctly reduce the payable (which was booked at this rate).
    # Only relevant when paying in the same foreign currency as the linked bill.
    booking_rate = pay_rate  # default: no FX diff
    if (
        payment.bill is not None
        and pay_currency != base
        and pay_currency == payment.bill.currency
    ):
        booking_rate = payment.bill.exchange_rate

    # ── Special case: base currency paying a foreign-currency bill ──────────
    # pay_currency = base (e.g. AFN), amount_tc = AFN amount, pay_rate = AFN/USD
    # The payable was recorded in USD; debit it in USD using today's rate so the
    # USD balance is reduced correctly. FX gain/loss vs booking rate is auto-booked.
    if (
        pay_currency == base
        and payment.bill is not None
        and payment.bill.currency != base
        and pay_rate > Decimal("0")
    ):
        bill_currency = payment.bill.currency
        bill_booking  = payment.bill.exchange_rate          # BC per 1 bill-TC (at invoice time)
        today_rate    = pay_rate                             # BC per 1 bill-TC (today)
        tc_cleared    = (amount_tc / today_rate).quantize(Decimal("0.01"))    # e.g. USD
        payable_dr_bc = (tc_cleared * bill_booking).quantize(Decimal("0.01")) # AFN at booking rate

        # Balance check: AFN leaving the cashbox = amount_tc (face value)
        balance = cashbox.account.balance()
        if amount_tc > balance:
            raise ValueError(
                f"Insufficient balance in '{cashbox.name}'. "
                f"Available: {balance:,.2f}, Required: {amount_tc:,.2f}."
            )

        je = _create_je(
            project, user, payment.date,
            f"Payment {payment.number} to {payment.contact.name}",
            "vendor_payment",
        )
        # Dr. Payable in bill currency at booking rate (clears USD balance correctly)
        _add_line(je, payment.contact.payable_account,
                  debit=tc_cleared, currency=bill_currency,
                  exchange_rate=bill_booking, debit_bc=payable_dr_bc)
        # Cr. Cashbox in base — cash leaves at face value
        _add_line(je, cashbox.account, credit=amount_tc, currency=base, exchange_rate=1)
        # Cr. FX Gain / Dr. FX Loss absorbs payable_dr_bc − amount_tc
        _fx_balance(je, project)
        _assert_balanced(je)

        payment.journal_entry = je
        payment.status = POSTED
        payment.save(update_fields=["journal_entry", "status"])
        return payment
    # ── end special case ────────────────────────────────────────────────────

    # payable_bc: BC amount the payable account decreases by (at booking rate)
    payable_bc = (amount_tc * booking_rate).quantize(Decimal("0.01"))

    # cashbox_bc: BC amount actually leaving the cashbox (at today's rate)
    if cb_currency == base:
        cashbox_bc = (amount_tc * pay_rate).quantize(Decimal("0.01"))
        cashbox_tc = cashbox_bc
        cashbox_rate = Decimal("1")
    elif cb_currency == pay_currency:
        # Same-currency cashbox (e.g. USD cashbox paying a USD bill)
        cashbox_tc = amount_tc
        cashbox_bc = (amount_tc * pay_rate).quantize(Decimal("0.01"))
        cashbox_rate = pay_rate
    else:
        # Cross-currency cashbox: leave BC = amount_tc × pay_rate
        cashbox_bc = (amount_tc * pay_rate).quantize(Decimal("0.01"))
        cashbox_tc = (cashbox_bc / pay_rate).quantize(Decimal("0.01")) if pay_rate else cashbox_bc
        cashbox_rate = pay_rate

    # Check cashbox balance
    balance = cashbox.account.balance()
    if cashbox_bc > balance:
        raise ValueError(
            f"Insufficient balance in '{cashbox.name}'. "
            f"Available: {balance:,.2f}, Required: {cashbox_bc:,.2f}."
        )

    je = _create_je(
        project, user, payment.date,
        f"Payment {payment.number} to {payment.contact.name}",
        "vendor_payment",
    )

    # Dr. Payable — reduce at booking rate (reflects original liability value)
    _add_line(je, payment.contact.payable_account,
              debit=amount_tc, currency=pay_currency,
              exchange_rate=booking_rate, debit_bc=payable_bc)

    # Cr. Cashbox — cash leaves at today's rate
    if cb_currency == base:
        _add_line(je, cashbox.account, credit=cashbox_bc,
                  currency=base, exchange_rate=1)
    else:
        _add_line(je, cashbox.account, credit=cashbox_tc,
                  currency=cb_currency, exchange_rate=cashbox_rate,
                  credit_bc=cashbox_bc)

    # Cr. FX Gain / Dr. FX Loss — absorbs any rate difference
    _fx_balance(je, project)
    _assert_balanced(je)

    payment.journal_entry = je
    payment.status = POSTED
    payment.save(update_fields=["journal_entry", "status"])
    return payment


# ---------------------------------------------------------------------------
# Receipt (customer → they pay us)
# ---------------------------------------------------------------------------

@db_transaction.atomic
def post_receipt(receipt: Receipt, user) -> Receipt:
    """
    Post a customer receipt.  Creates journal entry:

      Dr. cashbox.account             amount in cashbox currency
      [Dr. FX Loss / Cr. FX Gain]    if cashbox rate ≠ booking rate
      Cr. contact.receivable_account  amount (TC) × rate (BC)   [if contact set]
      Cr. receipt.income_account      same amount                [if no contact — walk-in]
    """
    _check_draft(receipt)

    # Determine the credit account
    if receipt.contact:
        if not receipt.contact.receivable_account:
            raise ValueError(
                f"Contact '{receipt.contact}' has no receivable account configured."
            )
        credit_account = receipt.contact.receivable_account
        je_desc = f"Receipt {receipt.number} from {receipt.contact.name}"
    else:
        if not receipt.income_account:
            raise ValueError(
                "Walk-in receipt requires an income account to be set."
            )
        credit_account = receipt.income_account
        je_desc = f"Receipt {receipt.number} — walk-in"

    project = receipt.project
    base = project.base_currency
    rec_currency = receipt.currency
    amount_tc = receipt.amount
    rec_rate = receipt.exchange_rate
    cashbox = receipt.cashbox
    cb_currency = cashbox.currency

    # Booking rate: BC per 1 invoice-currency unit at invoice time.
    # When receiving in the same foreign currency, the receivable was booked
    # at this rate; any difference vs today's rate is FX gain/loss.
    booking_rate = rec_rate  # default: no FX diff
    if (
        receipt.invoice is not None
        and rec_currency != base
        and rec_currency == receipt.invoice.currency
    ):
        booking_rate = receipt.invoice.exchange_rate

    # ── Special case: base currency received against a foreign-currency invoice ─
    # rec_currency = base (e.g. AFN), amount_tc = AFN amount, rec_rate = AFN/USD
    # The receivable was recorded in USD; credit it in USD so the balance reduces.
    if (
        rec_currency == base
        and receipt.invoice is not None
        and receipt.invoice.currency != base
        and rec_rate > Decimal("0")
    ):
        inv_currency  = receipt.invoice.currency
        inv_booking   = receipt.invoice.exchange_rate           # BC per 1 inv-TC at invoice time
        today_rate    = rec_rate                                 # BC per 1 inv-TC today
        tc_cleared    = (amount_tc / today_rate).quantize(Decimal("0.01"))     # e.g. USD
        receivable_cr_bc = (tc_cleared * inv_booking).quantize(Decimal("0.01")) # AFN at booking

        je = _create_je(project, user, receipt.date, je_desc, "project_income")
        # Dr. Cashbox — AFN arriving at face value
        _add_line(je, cashbox.account, debit=amount_tc, currency=base, exchange_rate=1)
        # Cr. Receivable in invoice currency at booking rate
        _add_line(je, credit_account,
                  credit=tc_cleared, currency=inv_currency,
                  exchange_rate=inv_booking, credit_bc=receivable_cr_bc)
        _fx_balance(je, project)
        _assert_balanced(je)

        receipt.journal_entry = je
        receipt.status = POSTED
        receipt.save(update_fields=["journal_entry", "status"])
        return receipt
    # ── end special case ────────────────────────────────────────────────────

    # receivable_bc: BC amount the receivable decreases by (at booking rate)
    receivable_bc = (amount_tc * booking_rate).quantize(Decimal("0.01"))

    if cb_currency == base:
        cashbox_bc = (amount_tc * rec_rate).quantize(Decimal("0.01"))
        cashbox_tc = cashbox_bc
        cashbox_rate = Decimal("1")
    elif cb_currency == rec_currency:
        cashbox_tc = amount_tc
        cashbox_bc = (amount_tc * rec_rate).quantize(Decimal("0.01"))
        cashbox_rate = rec_rate
    else:
        cashbox_bc = (amount_tc * rec_rate).quantize(Decimal("0.01"))
        cashbox_tc = cashbox_bc
        cashbox_rate = rec_rate

    je = _create_je(
        project, user, receipt.date,
        je_desc,
        "project_income",
    )

    # Dr. Cashbox — cash arrives at today's rate
    if cb_currency == base:
        _add_line(je, cashbox.account, debit=cashbox_bc, currency=base, exchange_rate=1)
    else:
        _add_line(je, cashbox.account, debit=cashbox_tc,
                  currency=cb_currency, exchange_rate=cashbox_rate,
                  debit_bc=cashbox_bc)

    # Cr. Receivable — reduce at booking rate (reflects original asset value)
    _add_line(je, credit_account,
              credit=amount_tc, currency=rec_currency,
              exchange_rate=booking_rate, credit_bc=receivable_bc)

    _fx_balance(je, project)
    _assert_balanced(je)

    receipt.journal_entry = je
    receipt.status = POSTED
    receipt.save(update_fields=["journal_entry", "status"])
    return receipt


# ---------------------------------------------------------------------------
# Reversal
# ---------------------------------------------------------------------------

@db_transaction.atomic
def reverse_vendor_bill(bill: VendorBill, user, date=None, notes="") -> VendorBill:
    """Create a reversal (credit note) for a posted bill."""
    _check_posted(bill)
    _check_not_reversed(bill)

    date = date or timezone.now().date()
    reversal = VendorBill.objects.create(
        project=bill.project,
        contact=bill.contact,
        date=date,
        due_date=date,
        currency=bill.currency,
        exchange_rate=bill.exchange_rate,
        status=DRAFT,
        notes=notes or f"Reversal of {bill.number}",
        created_by=user,
        reversal_of=bill,
    )
    for line in bill.lines.all():
        line.pk = None
        line.bill = reversal
        line.save()

    post_vendor_bill(reversal, user)
    # Also create a reversing JE that corrects the original
    reversal.journal_entry.corrects = bill.journal_entry
    reversal.journal_entry.save(update_fields=["corrects"])
    return reversal


@db_transaction.atomic
def reverse_customer_invoice(invoice: CustomerInvoice, user, date=None, notes="") -> CustomerInvoice:
    """Create a reversal (credit note) for a posted invoice."""
    _check_posted(invoice)
    _check_not_reversed(invoice)

    date = date or timezone.now().date()
    reversal = CustomerInvoice.objects.create(
        project=invoice.project,
        contact=invoice.contact,
        date=date,
        due_date=date,
        currency=invoice.currency,
        exchange_rate=invoice.exchange_rate,
        status=DRAFT,
        notes=notes or f"Reversal of {invoice.number}",
        created_by=user,
        reversal_of=invoice,
    )
    for line in invoice.lines.all():
        line.pk = None
        line.invoice = reversal
        line.save()

    post_customer_invoice(reversal, user)
    reversal.journal_entry.corrects = invoice.journal_entry
    reversal.journal_entry.save(update_fields=["corrects"])
    return reversal


@db_transaction.atomic
def reverse_payment(payment: Payment, user, date=None, notes="") -> Payment:
    """Create a reversal for a posted payment."""
    _check_posted(payment)
    _check_not_reversed(payment)

    date = date or timezone.now().date()
    reversal = Payment.objects.create(
        project=payment.project,
        contact=payment.contact,
        date=date,
        currency=payment.currency,
        exchange_rate=payment.exchange_rate,
        amount=payment.amount,
        cashbox=payment.cashbox,
        bill=payment.bill,
        status=DRAFT,
        notes=notes or f"Reversal of {payment.number}",
        created_by=user,
        reversal_of=payment,
    )
    post_payment(reversal, user)
    reversal.journal_entry.corrects = payment.journal_entry
    reversal.journal_entry.save(update_fields=["corrects"])
    return reversal


@db_transaction.atomic
def reverse_receipt(receipt: Receipt, user, date=None, notes="") -> Receipt:
    """Create a reversal for a posted receipt."""
    _check_posted(receipt)
    _check_not_reversed(receipt)

    date = date or timezone.now().date()
    reversal = Receipt.objects.create(
        project=receipt.project,
        contact=receipt.contact,
        date=date,
        currency=receipt.currency,
        exchange_rate=receipt.exchange_rate,
        amount=receipt.amount,
        cashbox=receipt.cashbox,
        invoice=receipt.invoice,
        status=DRAFT,
        notes=notes or f"Reversal of {receipt.number}",
        created_by=user,
        reversal_of=receipt,
    )
    post_receipt(reversal, user)
    reversal.journal_entry.corrects = receipt.journal_entry
    reversal.journal_entry.save(update_fields=["corrects"])
    return reversal
