"""Cashbox services."""
from django.db import transaction as db_transaction
from .models import Cashbox
from coa.services import create_cashbox_account


@db_transaction.atomic
def create_cashbox(project, name, currency):
    """Create a cashbox and its account."""
    cashbox = Cashbox(project=project, name=name, currency=currency)
    account = create_cashbox_account(project, cashbox)
    cashbox.account = account
    cashbox.save()
    return cashbox
