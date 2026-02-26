"""Cashbox services."""
from django.db import transaction as db_transaction
from django.core.exceptions import PermissionDenied
from .models import Cashbox
from coa.services import create_cashbox_account
from projects.permissions import assert_can_do_accounting


@db_transaction.atomic
def create_cashbox(project, user, name, currency):
    """Create a cashbox and its account. Requires accounting permission."""
    assert_can_do_accounting(user, project)
    cashbox = Cashbox(project=project, name=name, currency=currency)
    account = create_cashbox_account(project, cashbox)
    cashbox.account = account
    cashbox.save()
    return cashbox
