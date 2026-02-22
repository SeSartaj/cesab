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


def _add_line(je, account, debit=0, credit=0, currency=None, exchange_rate=1):
    if currency is None:
        currency = je.project.base_currency
    rate = Decimal(str(exchange_rate))
    d = Decimal(str(debit))
    c = Decimal(str(credit))
    JournalLine.objects.create(
        journal_entry=je,
        account=account,
        debit=d * rate if rate != 1 else d,
        credit=c * rate if rate != 1 else c,
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
    je = _create_je(project, user, date, description or f"Capital contribution by {project_partner.partner.name}",
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
    je = _create_je(project, user, date, description or f"Withdrawal by {project_partner.partner.name}",
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
    _check_cashbox_balance(cashbox, Decimal(str(amount)) * Decimal(str(exchange_rate)))
    je = _create_je(project, user, date, description or f"Advance to {vendor.name}",
                    "vendor_advance")
    _add_line(je, vendor.advance_account, debit=amount, currency=currency, exchange_rate=exchange_rate)
    _add_line(je, cashbox.account, credit=amount, currency=currency, exchange_rate=exchange_rate)
    return je


def vendor_payment_against_bill(project, user, date, vendor, amount, cashbox,
                                description="", currency=None, exchange_rate=1):
    """
    Payment against vendor bill.
    The payable is always reduced at the weighted-average rate of the outstanding
    payable balance (i.e. the original bill rate). Any difference between that
    and the current payment rate goes to FX Gain or FX Loss.

    Dr. Vendor Payable Account   (at weighted-average bill rate)
    Dr. FX Loss Account          (when payment rate > bill rate — we pay more)
    Cr. FX Gain Account          (when payment rate < bill rate — we pay less)
    Cr. Cashbox Account          (at current payment rate)
    """
    from coa.services import get_or_create_fx_accounts
    from django.db.models import Sum

    currency = currency or project.base_currency
    payment_rate = Decimal(str(exchange_rate))
    amount_tc = Decimal(str(amount))

    # Weighted-average rate of the outstanding payable (= original bill rate)
    # Only relevant when a foreign currency is involved (payment_rate != 1).
    bill_rate = payment_rate  # default: no FX difference
    fx_diff = Decimal("0")

    if payment_rate != Decimal("1"):
        agg = JournalLine.objects.filter(account=vendor.payable_account).aggregate(
            bc_credit=Sum("credit"),
            bc_debit=Sum("debit"),
            tc_credit=Sum("credit_tc"),
            tc_debit=Sum("debit_tc"),
        )
        outstanding_bc = (agg["bc_credit"] or Decimal("0")) - (agg["bc_debit"] or Decimal("0"))
        outstanding_tc = (agg["tc_credit"] or Decimal("0")) - (agg["tc_debit"] or Decimal("0"))

        if outstanding_tc > Decimal("0"):
            bill_rate = (outstanding_bc / outstanding_tc).quantize(Decimal("0.000001"))

        payable_debit_bc = (amount_tc * bill_rate).quantize(Decimal("0.01"))
        cashbox_credit_bc = (amount_tc * payment_rate).quantize(Decimal("0.01"))
        fx_diff = payable_debit_bc - cashbox_credit_bc  # >0 = gain, <0 = loss

    _check_cashbox_balance(cashbox, (amount_tc * payment_rate).quantize(Decimal("0.01")))

    je = _create_je(project, user, date, description or f"Payment to {vendor.name}",
                    "vendor_payment")

    # Reduce payable at the original bill rate
    _add_line(je, vendor.payable_account, debit=amount_tc, currency=currency, exchange_rate=bill_rate)

    # Book exchange difference if any
    if fx_diff != Decimal("0"):
        gain_acc, loss_acc = get_or_create_fx_accounts(project)
        if fx_diff > 0:
            # We owe more (BC) than we actually pay → FX Gain
            _add_line(je, gain_acc, credit=fx_diff,
                      currency=project.base_currency, exchange_rate=1)
        else:
            # We pay more (BC) than the book value of the payable → FX Loss
            _add_line(je, loss_acc, debit=-fx_diff,
                      currency=project.base_currency, exchange_rate=1)

    # Pay from cashbox at the current payment rate
    _add_line(je, cashbox.account, credit=amount_tc, currency=currency, exchange_rate=payment_rate)

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


def cashbox_transfer(project, user, date, from_cashbox, to_cashbox, amount,
                     description="", currency=None, exchange_rate=1):
    """
    Transfer between cashboxes.
    Dr. To Cashbox Account
    Cr. From Cashbox Account
    """
    currency = currency or project.base_currency
    _check_cashbox_balance(from_cashbox, Decimal(str(amount)) * Decimal(str(exchange_rate)))
    je = _create_je(project, user, date,
                    description or f"Transfer from {from_cashbox.name} to {to_cashbox.name}",
                    "cashbox_transfer")
    _add_line(je, to_cashbox.account, debit=amount, currency=currency, exchange_rate=exchange_rate)
    _add_line(je, from_cashbox.account, credit=amount, currency=currency, exchange_rate=exchange_rate)
    return je


def bank_deposit(project, user, date, from_cashbox, to_cashbox, amount,
                 description="", currency=None, exchange_rate=1):
    """
    Bank deposit or cash withdrawal (same as cashbox transfer).
    Dr. To Account (bank or cash)
    Cr. From Account
    """
    currency = currency or project.base_currency
    _check_cashbox_balance(from_cashbox, Decimal(str(amount)) * Decimal(str(exchange_rate)))
    je = _create_je(project, user, date,
                    description or f"Deposit/Withdrawal",
                    "bank_deposit")
    _add_line(je, to_cashbox.account, debit=amount, currency=currency, exchange_rate=exchange_rate)
    _add_line(je, from_cashbox.account, credit=amount, currency=currency, exchange_rate=exchange_rate)
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
    """
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
    _check_cashbox_balance(cashbox, Decimal(str(amount)) * Decimal(str(exchange_rate)))
    je = _create_je(project, user, date,
                    description or f"Direct payment to {vendor.name}",
                    "vendor_direct_payment")
    _add_line(je, expense_account, debit=amount, currency=currency, exchange_rate=exchange_rate)
    _add_line(je, cashbox.account, credit=amount, currency=currency, exchange_rate=exchange_rate)
    return je


def vendor_refund(project, user, date, vendor, amount, cashbox,
                  description="", currency=None, exchange_rate=1):
    """
    Vendor refunds money back.
    Dr. Cashbox Account
    Cr. Vendor Payable Account
    """
    currency = currency or project.base_currency
    je = _create_je(project, user, date,
                    description or f"Refund from {vendor.name}",
                    "vendor_refund")
    _add_line(je, cashbox.account, debit=amount, currency=currency, exchange_rate=exchange_rate)
    _add_line(je, vendor.payable_account, credit=amount, currency=currency, exchange_rate=exchange_rate)
    return je


def create_correction_entry(original_je, user, description=""):
    """
    Create a counter-balancing correction entry that reverses the original.
    All debits become credits and vice versa.
    Users can never delete journal entries — they can only correct them.
    """
    from django.utils import timezone
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
