"""
Transaction services - business logic for all transaction types.
All journal entries are created here.
"""
from decimal import Decimal
from django.utils import timezone
from journal.models import JournalEntry, JournalLine
from coa.models import Account


def _create_je(project, user, date, description, transaction_type, reference=""):
    return JournalEntry.objects.create(
        project=project,
        date=date,
        description=description,
        transaction_type=transaction_type,
        reference=reference,
        created_by=user,
    )


def _check_cashbox_balance(cashbox, amount_bc):
    """Raise ValueError if cashbox has insufficient balance (in base currency)."""
    balance = cashbox.account.balance()
    if Decimal(str(amount_bc)) > balance:
        raise ValueError(
            f"Insufficient balance in '{cashbox.name}'. "
            f"Available: {balance:,.2f}, Required: {amount_bc:,.2f}."
        )


def _add_line(je, account, debit=0, credit=0, currency=None, exchange_rate=1,
              debit_bc=None, credit_bc=None):
    """Create a JournalLine.

    *debit* / *credit* are **transaction-currency** amounts.
    BC is normally computed as TC × rate, but callers can pass explicit
    *debit_bc* / *credit_bc* to avoid round-trip rounding drift
    (e.g. when TC was derived by dividing a BC amount by the rate).
    """
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


def capital_contribution(project, user, date, project_partner, amount,
                         cashbox, description="", currency=None, exchange_rate=1):
    """
    Partner contributes capital to the project.
    Dr. Cashbox Account
    Cr. Partner Capital Account
    """
    currency = currency or project.base_currency
    je = _create_je(project, user, date, description or f"Capital contribution by {project_partner.name}",
                    "capital_contribution")
    _add_line(je, cashbox.account, debit=amount, currency=currency, exchange_rate=exchange_rate)
    _add_line(je, project_partner.capital_account, credit=amount, currency=currency, exchange_rate=exchange_rate)
    return je


def shareholder_withdrawal(project, user, date, project_partner, amount,
                           cashbox, description="", currency=None, exchange_rate=1):
    """
    Partner withdraws from project.
    Dr. Partner Current Account
    Cr. Cashbox Account
    """
    currency = currency or project.base_currency
    _check_cashbox_balance(cashbox, Decimal(str(amount)) * Decimal(str(exchange_rate)))
    je = _create_je(project, user, date, description or f"Withdrawal by {project_partner.name}",
                    "shareholder_withdrawal")
    _add_line(je, project_partner.current_account, debit=amount, currency=currency, exchange_rate=exchange_rate)
    _add_line(je, cashbox.account, credit=amount, currency=currency, exchange_rate=exchange_rate)
    return je


def vendor_bill(project, user, date, vendor, expense_account, amount,
                description="", currency=None, exchange_rate=1):
    """
    Vendor bill / expense on credit.
    Dr. Expense Account
    Cr. Vendor Payable Account
    """
    currency = currency or project.base_currency
    je = _create_je(project, user, date, description or f"Bill from {vendor.name}",
                    "vendor_bill")
    _add_line(je, expense_account, debit=amount, currency=currency, exchange_rate=exchange_rate)
    _add_line(je, vendor.payable_account, credit=amount, currency=currency, exchange_rate=exchange_rate)
    return je


def vendor_advance_payment(project, user, date, vendor, amount, cashbox,
                           description="", currency=None, exchange_rate=1):
    """
    Advance payment to vendor.
    Dr. Vendor Advance Account
    Cr. Cashbox Account
    """
    currency = currency or project.base_currency
    cashbox_bc = (Decimal(str(amount)) * Decimal(str(exchange_rate))).quantize(Decimal("0.01"))
    _check_cashbox_balance(cashbox, cashbox_bc)
    je = _create_je(project, user, date, description or f"Advance to {vendor.name}",
                    "vendor_advance")
    _add_line(je, vendor.advance_account, debit=amount, currency=currency, exchange_rate=exchange_rate)
    _add_line(je, cashbox.account, credit=cashbox_bc, currency=project.base_currency, exchange_rate=1)
    return je


def vendor_payment_against_bill(project, user, date, vendor, amount, cashbox,
                                description="", currency=None, exchange_rate=1):
    """
    Payment against vendor bill.

    Two cashbox scenarios for a foreign-currency (e.g. USD) payable:

    A) Same-currency cashbox (USD cashbox paying a USD bill):
       No conversion happens at payment time.  The caller need not supply an
       exchange rate — the original booking rate is used automatically.
       Dr. Vendor Payable   (amount_tc × bill_rate  → BC)
       Cr. USD Cashbox      (amount_tc × bill_rate  → BC, TC in USD)

    B) Base-currency cashbox (AFN cashbox paying a USD bill):
       The user supplies today's exchange rate.  Any difference vs the booking
       rate goes to FX Gain / FX Loss.
       Dr. Vendor Payable   (amount_tc × bill_rate  → BC)
       Dr. FX Loss          (only when paying at a worse rate than booked)
       Cr. FX Gain          (only when paying at a better rate than booked)
       Cr. AFN Cashbox      (amount_tc × payment_rate → BC, TC in AFN)

    When the payable is already in base currency there is no FX difference.
    """
    from coa.services import get_or_create_fx_accounts
    from django.db.models import Sum

    currency = currency or project.base_currency
    payment_rate = Decimal(str(exchange_rate))
    amount_tc = Decimal(str(amount))

    bill_rate = Decimal("1")
    fx_diff   = Decimal("0")
    payable_in_foreign = False
    cashbox_bc = Decimal("0")  # BC amount leaving the cashbox

    if currency != project.base_currency:
        # Scenarios A / B: the bill was recorded in a foreign currency.
        # Aggregate only lines in the payment currency to avoid mixing AFN+USD totals.
        agg = JournalLine.objects.active().filter(
            account=vendor.payable_account,
            transaction_currency=currency,
        ).aggregate(
            bc_credit=Sum("credit"),
            bc_debit=Sum("debit"),
            tc_credit=Sum("credit_tc"),
            tc_debit=Sum("debit_tc"),
        )
        outstanding_bc = (agg["bc_credit"] or Decimal("0")) - (agg["bc_debit"] or Decimal("0"))
        outstanding_tc = (agg["tc_credit"] or Decimal("0")) - (agg["tc_debit"] or Decimal("0"))

        if outstanding_tc > Decimal("0"):
            payable_in_foreign = True
            bill_rate = (outstanding_bc / outstanding_tc).quantize(Decimal("0.000001"))

            # Scenario A: same-currency cashbox (e.g. USD cashbox paying a USD bill).
            # Auto-use the booking rate — caller need not supply an exchange rate.
            if cashbox.currency == currency:
                payment_rate = bill_rate

            payable_debit_bc = (amount_tc * bill_rate).quantize(Decimal("0.01"))
            cashbox_bc       = (amount_tc * payment_rate).quantize(Decimal("0.01"))
            fx_diff          = payable_debit_bc - cashbox_bc  # >0 = gain, <0 = loss

    elif cashbox.currency != project.base_currency:
        # Scenario C: bill is in base currency (AFN) but cashbox is foreign (USD).
        # The user supplies the spot rate (BC per 1 cashbox-currency unit).
        # We work out how many foreign units the cashbox gives up to cover the AFN payable.
        if payment_rate <= Decimal("0"):
            raise ValueError("Exchange rate must be greater than zero.")
        cashbox_foreign_tc = (amount_tc / payment_rate).quantize(Decimal("0.01"))
        # Pin BC to the exact payable amount — do NOT recompute from the
        # rounded cashbox_foreign_tc, which introduces a round-trip error
        # (e.g. 491 000 / 63 → 7 793.65 → × 63 = 490 999.95).
        cashbox_bc = amount_tc

    else:
        # Normal: both bill and cashbox are in base currency — no conversion.
        cashbox_bc = amount_tc

    _check_cashbox_balance(cashbox, cashbox_bc)

    je = _create_je(project, user, date, description or f"Payment to {vendor.name}",
                    "vendor_payment")

    # Reduce payable
    if payable_in_foreign:
        _add_line(je, vendor.payable_account, debit=amount_tc, currency=currency, exchange_rate=bill_rate)
    else:
        _add_line(je, vendor.payable_account, debit=cashbox_bc,
                  currency=project.base_currency, exchange_rate=1)

    # Book exchange difference if any (only for foreign-currency payables, scenario B)
    if fx_diff != Decimal("0"):
        gain_acc, loss_acc = get_or_create_fx_accounts(project)
        if fx_diff > 0:
            _add_line(je, gain_acc, credit=fx_diff,
                      currency=project.base_currency, exchange_rate=1)
        else:
            _add_line(je, loss_acc, debit=-fx_diff,
                      currency=project.base_currency, exchange_rate=1)

    # Cashbox line — record in the cashbox's own currency so TC balances are meaningful.
    #   Scenario A (USD cashbox, USD bill): TC = amount_tc USD
    #   Scenario B (AFN cashbox, USD bill): TC = cashbox_bc AFN
    #   Scenario C (USD cashbox, AFN bill): TC = cashbox_foreign_tc USD  (computed above)
    #   Normal    (AFN cashbox, AFN bill): TC = cashbox_bc AFN
    if cashbox.currency != project.base_currency:
        if payable_in_foreign:
            # Scenarios A/B: amount_tc is already expressed in the foreign bill currency.
            _add_line(je, cashbox.account, credit=amount_tc,
                      currency=cashbox.currency, exchange_rate=payment_rate)
        else:
            # Scenario C: amount_tc is AFN; give the pre-computed foreign TC amount.
            # Pass credit_bc to pin BC to the exact payable (avoids rounding drift).
            _add_line(je, cashbox.account, credit=cashbox_foreign_tc,
                      currency=cashbox.currency, exchange_rate=payment_rate,
                      credit_bc=amount_tc)
    else:
        _add_line(je, cashbox.account, credit=cashbox_bc,
                  currency=project.base_currency, exchange_rate=1)

    return je


def cash_expense(project, user, date, expense_account, amount, cashbox,
                 description="", currency=None, exchange_rate=1):
    """
    Cash expense paid from cashbox.
    Dr. Expense Account
    Cr. Cashbox Account
    """
    currency = currency or project.base_currency
    _check_cashbox_balance(cashbox, Decimal(str(amount)) * Decimal(str(exchange_rate)))
    je = _create_je(project, user, date, description or "Cash expense",
                    "cash_expense")
    _add_line(je, expense_account, debit=amount, currency=currency, exchange_rate=exchange_rate)
    _add_line(je, cashbox.account, credit=amount, currency=currency, exchange_rate=exchange_rate)
    return je


def cashbox_transfer(project, user, date, from_cashbox, to_cashbox,
                     from_amount, from_rate=1, to_rate=None, description=""):
    """
    Transfer between cashboxes, fully supporting cross-currency transfers.
    Each leg is booked in the cashbox's own currency so balances always
    display correctly in the cashbox detail view.

    from_amount : amount in from_cashbox.currency
    from_rate   : base-currency units per 1 from_cashbox.currency unit
                  (required when from_cashbox is not base-currency; default 1)
    to_rate     : base-currency units per 1 to_cashbox.currency unit
                  (required when to_cashbox is non-base AND a different
                   currency from from_cashbox; defaults to from_rate)

    Dr. To Cashbox Account   (in to_cashbox currency)
    Cr. From Cashbox Account (in from_cashbox currency)
    """
    base         = project.base_currency
    from_currency = from_cashbox.currency
    to_currency   = to_cashbox.currency

    from_amount = Decimal(str(from_amount))
    from_rate   = Decimal(str(from_rate or 1))

    # If both cashboxes share the same non-base currency, use the same rate
    if to_rate is None or to_currency == from_currency:
        to_rate = from_rate
    else:
        to_rate = Decimal(str(to_rate))

    # BC value that must be equal on both legs (the pivot)
    bc_amount = (
        from_amount
        if from_currency == base
        else (from_amount * from_rate).quantize(Decimal("0.01"))
    )
    # Amount arriving at the to_cashbox in its own currency
    to_amount = (
        bc_amount
        if to_currency == base
        else (bc_amount / to_rate).quantize(Decimal("0.01"))
    )

    _check_cashbox_balance(from_cashbox, bc_amount)

    je = _create_je(
        project, user, date,
        description or f"Transfer: {from_cashbox.name} → {to_cashbox.name}",
        "cashbox_transfer",
    )

    # FROM leg: credit from_cashbox in its own currency
    if from_currency == base:
        _add_line(je, from_cashbox.account, credit=from_amount, currency=base, exchange_rate=1)
    else:
        _add_line(je, from_cashbox.account, credit=from_amount,
                  currency=from_currency, exchange_rate=from_rate)

    # TO leg: debit to_cashbox in its own currency
    if to_currency == base:
        _add_line(je, to_cashbox.account, debit=bc_amount, currency=base, exchange_rate=1)
    else:
        _add_line(je, to_cashbox.account, debit=to_amount,
                  currency=to_currency, exchange_rate=to_rate)

    # FX rounding: the division bc_amount/to_rate is rounded to 2 d.p., so the
    # actual BC value of the debit leg may differ from bc_amount by a few cents.
    # Absorb that difference in FX Gain (4200) / FX Loss (5600) so the JE balances.
    from django.db.models import Sum as _Sum
    from coa.services import get_or_create_fx_accounts
    totals   = je.lines.aggregate(d=_Sum("debit"), c=_Sum("credit"))
    fx_diff  = (totals["d"] or Decimal("0")) - (totals["c"] or Decimal("0"))
    if fx_diff != Decimal("0"):
        gain_acc, loss_acc = get_or_create_fx_accounts(project)
        if fx_diff > 0:
            # Debit side is larger → credit FX Gain to balance
            _add_line(je, gain_acc, credit=fx_diff, currency=base, exchange_rate=1)
        else:
            # Credit side is larger → debit FX Loss to balance
            _add_line(je, loss_acc, debit=-fx_diff, currency=base, exchange_rate=1)

    return je


def bank_deposit(project, user, date, from_cashbox, to_cashbox,
                 from_amount, from_rate=1, to_rate=None, description=""):
    """
    Bank deposit or cash withdrawal — same two-leg cross-currency logic
    as cashbox_transfer but tagged with a different transaction type.
    Dr. To Account (bank or cash)  (in to_cashbox currency)
    Cr. From Account               (in from_cashbox currency)
    """
    base         = project.base_currency
    from_currency = from_cashbox.currency
    to_currency   = to_cashbox.currency

    from_amount = Decimal(str(from_amount))
    from_rate   = Decimal(str(from_rate or 1))

    if to_rate is None or to_currency == from_currency:
        to_rate = from_rate
    else:
        to_rate = Decimal(str(to_rate))

    bc_amount = (
        from_amount
        if from_currency == base
        else (from_amount * from_rate).quantize(Decimal("0.01"))
    )
    to_amount = (
        bc_amount
        if to_currency == base
        else (bc_amount / to_rate).quantize(Decimal("0.01"))
    )

    _check_cashbox_balance(from_cashbox, bc_amount)

    je = _create_je(
        project, user, date,
        description or "Deposit / Withdrawal",
        "bank_deposit",
    )

    if from_currency == base:
        _add_line(je, from_cashbox.account, credit=from_amount, currency=base, exchange_rate=1)
    else:
        _add_line(je, from_cashbox.account, credit=from_amount,
                  currency=from_currency, exchange_rate=from_rate)

    if to_currency == base:
        _add_line(je, to_cashbox.account, debit=bc_amount, currency=base, exchange_rate=1)
    else:
        _add_line(je, to_cashbox.account, debit=to_amount,
                  currency=to_currency, exchange_rate=to_rate)

    # FX rounding adjustment — same logic as cashbox_transfer
    from django.db.models import Sum as _Sum
    from coa.services import get_or_create_fx_accounts
    totals   = je.lines.aggregate(d=_Sum("debit"), c=_Sum("credit"))
    fx_diff  = (totals["d"] or Decimal("0")) - (totals["c"] or Decimal("0"))
    if fx_diff != Decimal("0"):
        gain_acc, loss_acc = get_or_create_fx_accounts(project)
        if fx_diff > 0:
            _add_line(je, gain_acc, credit=fx_diff, currency=base, exchange_rate=1)
        else:
            _add_line(je, loss_acc, debit=-fx_diff, currency=base, exchange_rate=1)

    return je


def project_income(project, user, date, cashbox, amount, income_account=None,
                   description="", currency=None, exchange_rate=1):
    """
    Project income / service revenue.
    Dr. Cashbox Account
    Cr. Revenue Account
    """
    currency = currency or project.base_currency
    if income_account is None:
        income_account = Account.objects.filter(project=project, code="4100").first()
    je = _create_je(project, user, date, description or "Project income",
                    "project_income")
    _add_line(je, cashbox.account, debit=amount, currency=currency, exchange_rate=exchange_rate)
    _add_line(je, income_account, credit=amount, currency=currency, exchange_rate=exchange_rate)
    return je


def asset_purchase(project, user, date, asset_account, amount, cashbox,
                   description="", currency=None, exchange_rate=1):
    """
    Asset purchase (equipment, tools).
    Dr. Asset Account
    Cr. Cashbox Account
    """
    currency = currency or project.base_currency
    _check_cashbox_balance(cashbox, Decimal(str(amount)) * Decimal(str(exchange_rate)))
    je = _create_je(project, user, date, description or "Asset purchase",
                    "asset_purchase")
    _add_line(je, asset_account, debit=amount, currency=currency, exchange_rate=exchange_rate)
    _add_line(je, cashbox.account, credit=amount, currency=currency, exchange_rate=exchange_rate)
    return je


def pay_salary(project, user, date, employee, days_or_months, cashbox,
               description="", currency=None, exchange_rate=1):
    """
    Pay employee salary.
    Dr. Salary Expense Account
    Cr. Cashbox Account (if paid directly)
    """
    currency = currency or project.base_currency
    amount = employee.salary_amount * Decimal(str(days_or_months))
    _check_cashbox_balance(cashbox, amount * Decimal(str(exchange_rate)))
    je = _create_je(project, user, date,
                    description or f"Salary for {employee.name}",
                    "pay_salary")
    _add_line(je, employee.expense_account, debit=amount, currency=currency, exchange_rate=exchange_rate)
    _add_line(je, cashbox.account, credit=amount, currency=currency, exchange_rate=exchange_rate)
    return je


def manual_journal_entry(project, user, date, description, lines):
    """
    Manual journal entry with multiple lines.
    lines: list of dicts: {account_id, debit, credit, currency_id, exchange_rate}

    Raises ValueError if lines are empty or debit/credit totals don't balance
    (amounts in each line dict are treated as base-currency values).
    """
    if not lines:
        raise ValueError("At least one journal line is required.")

    total_debit  = sum(Decimal(str(l.get("debit",  0))) for l in lines)
    total_credit = sum(Decimal(str(l.get("credit", 0))) for l in lines)
    if total_debit != total_credit:
        raise ValueError(
            f"Journal entry is not balanced — "
            f"Debit {total_debit:,.2f} ≠ Credit {total_credit:,.2f}."
        )

    je = _create_je(project, user, date, description, "manual")
    for line in lines:
        account = Account.objects.get(pk=line["account_id"])
        currency_id = line.get("currency_id")
        if currency_id:
            from core.models import Currency
            currency = Currency.objects.get(pk=currency_id)
        else:
            currency = project.base_currency
        JournalLine.objects.create(
            journal_entry=je,
            account=account,
            debit=Decimal(str(line.get("debit", 0))),
            credit=Decimal(str(line.get("credit", 0))),
            transaction_currency=currency,
            exchange_rate=Decimal(str(line.get("exchange_rate", 1))),
            debit_tc=Decimal(str(line.get("debit_tc", line.get("debit", 0)))),
            credit_tc=Decimal(str(line.get("credit_tc", line.get("credit", 0)))),
            description=line.get("description", ""),
        )
    return je


def vendor_advance_settlement(project, user, date, vendor, amount,
                               description="", currency=None, exchange_rate=1):
    """
    Settle vendor advance against payable balance.
    Dr. Vendor Payable Account
    Cr. Vendor Advance Account
    """
    currency = currency or project.base_currency
    je = _create_je(project, user, date,
                    description or f"Advance settlement for {vendor.name}",
                    "vendor_advance_settlement")
    _add_line(je, vendor.payable_account, debit=amount, currency=currency, exchange_rate=exchange_rate)
    _add_line(je, vendor.advance_account, credit=amount, currency=currency, exchange_rate=exchange_rate)
    return je


def vendor_direct_payment(project, user, date, vendor, expense_account, amount, cashbox,
                           description="", currency=None, exchange_rate=1):
    """
    Pay vendor directly without a bill (direct cash payment).
    Dr. Expense Account
    Cr. Cashbox Account
    """
    currency = currency or project.base_currency
    cashbox_bc = (Decimal(str(amount)) * Decimal(str(exchange_rate))).quantize(Decimal("0.01"))
    _check_cashbox_balance(cashbox, cashbox_bc)
    je = _create_je(project, user, date,
                    description or f"Direct payment to {vendor.name}",
                    "vendor_direct_payment")
    _add_line(je, expense_account, debit=amount, currency=currency, exchange_rate=exchange_rate)
    _add_line(je, cashbox.account, credit=cashbox_bc, currency=project.base_currency, exchange_rate=1)
    return je


def vendor_refund(project, user, date, vendor, amount, cashbox,
                  description="", currency=None, exchange_rate=1):
    """
    Vendor refunds money back.
    Dr. Cashbox Account
    Cr. Vendor Payable Account
    """
    currency = currency or project.base_currency
    cashbox_bc = (Decimal(str(amount)) * Decimal(str(exchange_rate))).quantize(Decimal("0.01"))
    je = _create_je(project, user, date,
                    description or f"Refund from {vendor.name}",
                    "vendor_refund")
    _add_line(je, cashbox.account, debit=cashbox_bc, currency=project.base_currency, exchange_rate=1)
    _add_line(je, vendor.payable_account, credit=amount, currency=currency, exchange_rate=exchange_rate)
    return je


def create_correction_entry(original_je, user, description=""):
    """
    Create a counter-balancing correction entry that reverses the original.
    All debits become credits and vice versa.
    Users can never delete journal entries — they can only correct them.
    Raises ValueError if the entry is already a correction or has already been corrected.
    """
    from django.utils import timezone
    if original_je.corrects_id is not None:
        raise ValueError("A correction entry cannot itself be corrected.")
    if original_je.corrections.exists():
        raise ValueError("This entry has already been corrected and cannot be corrected again.")
    project = original_je.project
    je = JournalEntry.objects.create(
        project=project,
        date=timezone.now().date(),
        description=description or f"Correction for JE-{original_je.pk:04d}: {original_je.description}",
        transaction_type="correction",
        corrects=original_je,
        created_by=user,
    )
    for line in original_je.lines.all():
        JournalLine.objects.create(
            journal_entry=je,
            account=line.account,
            debit=line.credit,    # swap
            credit=line.debit,    # swap
            transaction_currency=line.transaction_currency,
            exchange_rate=line.exchange_rate,
            debit_tc=line.credit_tc,
            credit_tc=line.debit_tc,
            description=f"Correction: {line.description}",
        )
    return je
