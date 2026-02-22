"""
Inventory services — business logic for inventory management.
All accounting entries are created here.
"""
from decimal import Decimal
from django.db import transaction as db_transaction
from django.utils import timezone

from journal.models import JournalEntry, JournalLine
from .models import InventoryItem, InventoryMovement


def _create_je(project, user, date, description, transaction_type):
    return JournalEntry.objects.create(
        project=project,
        date=date,
        description=description,
        transaction_type=transaction_type,
        created_by=user,
    )


def _add_line(je, account, debit=0, credit=0, currency=None, exchange_rate=1):
    currency = currency or je.project.base_currency
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


@db_transaction.atomic
def record_inventory_purchase(project, user, date, item, quantity, unit_cost,
                               cashbox, description="", currency=None, exchange_rate=1):
    """
    Purchase inventory with cash.
    Dr. Inventory Asset Account
    Cr. Cashbox Account
    """
    currency = currency or project.base_currency
    rate = Decimal(str(exchange_rate))
    qty = Decimal(str(quantity))
    cost = Decimal(str(unit_cost))
    total = (qty * cost * rate).quantize(Decimal("0.01"))

    je = _create_je(
        project, user, date,
        description or f"Inventory purchase: {item.name} x {quantity} {item.unit}",
        "inventory_purchase",
    )
    _add_line(je, item.inventory_account, debit=qty * cost, currency=currency, exchange_rate=exchange_rate)
    _add_line(je, cashbox.account, credit=qty * cost, currency=currency, exchange_rate=exchange_rate)

    InventoryMovement.objects.create(
        project=project,
        item=item,
        movement_type="purchase",
        quantity=qty,
        unit_cost=cost,
        total_cost=total,
        journal_entry=je,
        created_by=user,
    )
    return je


@db_transaction.atomic
def record_inventory_consumption(project, user, date, item, quantity,
                                  description=""):
    """
    Consume inventory (expense it) using weighted average cost.
    Dr. Expense Account
    Cr. Inventory Asset Account
    """
    qty = Decimal(str(quantity))
    cost = item.weighted_average_cost()
    total = (qty * cost).quantize(Decimal("0.01"))

    je = _create_je(
        project, user, date,
        description or f"Inventory consumed: {item.name} x {quantity} {item.unit}",
        "inventory_consumption",
    )
    _add_line(je, item.expense_account, debit=qty * cost, currency=project.base_currency)
    _add_line(je, item.inventory_account, credit=qty * cost, currency=project.base_currency)

    InventoryMovement.objects.create(
        project=project,
        item=item,
        movement_type="consumption",
        quantity=qty,
        unit_cost=cost,
        total_cost=total,
        journal_entry=je,
        created_by=user,
    )
    return je


@db_transaction.atomic
def record_inventory_adjustment(project, user, date, item, quantity, unit_cost,
                                 is_increase=True, description=""):
    """
    Adjust inventory quantity (increase or decrease).
    Increase: Dr. Inventory Account
    Decrease: Dr. Expense Account  Cr. Inventory Account
    """
    qty = Decimal(str(quantity))
    cost = Decimal(str(unit_cost))
    total = (qty * cost).quantize(Decimal("0.01"))

    je = _create_je(
        project, user, date,
        description or f"Inventory adjustment: {item.name}",
        "inventory_adjustment",
    )
    if is_increase:
        _add_line(je, item.inventory_account, debit=qty * cost, currency=project.base_currency)
        # Credit a suspense / adjustment account — use expense account for simplicity
        _add_line(je, item.expense_account, credit=qty * cost, currency=project.base_currency)
    else:
        _add_line(je, item.expense_account, debit=qty * cost, currency=project.base_currency)
        _add_line(je, item.inventory_account, credit=qty * cost, currency=project.base_currency)

    InventoryMovement.objects.create(
        project=project,
        item=item,
        movement_type="adjustment",
        quantity=qty if is_increase else -qty,
        unit_cost=cost,
        total_cost=total,
        journal_entry=je,
        created_by=user,
    )
    return je


@db_transaction.atomic
def record_partner_inventory_contribution(project, user, date, item, quantity, unit_cost,
                                           project_partner, description="",
                                           currency=None, exchange_rate=1):
    """
    Partner contributes inventory instead of cash.
    Dr. Inventory Asset Account
    Cr. Partner Capital Account
    """
    currency = currency or project.base_currency
    rate = Decimal(str(exchange_rate))
    qty = Decimal(str(quantity))
    cost = Decimal(str(unit_cost))
    total = (qty * cost * rate).quantize(Decimal("0.01"))

    je = _create_je(
        project, user, date,
        description or f"Partner inventory contribution: {project_partner.partner.name} — {item.name} x {quantity}",
        "partner_inventory_contribution",
    )
    _add_line(je, item.inventory_account, debit=qty * cost, currency=currency, exchange_rate=exchange_rate)
    _add_line(je, project_partner.capital_account, credit=qty * cost, currency=currency, exchange_rate=exchange_rate)

    InventoryMovement.objects.create(
        project=project,
        item=item,
        movement_type="contribution",
        quantity=qty,
        unit_cost=cost,
        total_cost=total,
        project_partner=project_partner,
        journal_entry=je,
        created_by=user,
    )
    return je


@db_transaction.atomic
def create_inventory_item(project, name, unit, inventory_account=None, expense_account=None):
    """Create a new inventory item, auto-creating accounts if not provided."""
    from coa.services import create_inventory_accounts
    if inventory_account is None or expense_account is None:
        inv_acc, exp_acc = create_inventory_accounts(project, name)
        inventory_account = inventory_account or inv_acc
        expense_account = expense_account or exp_acc

    item = InventoryItem.objects.create(
        project=project,
        name=name,
        unit=unit,
        inventory_account=inventory_account,
        expense_account=expense_account,
    )
    return item
