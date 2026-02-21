"""Vendor services."""
from django.db import transaction as db_transaction
from .models import Vendor
from coa.services import create_vendor_accounts


@db_transaction.atomic
def create_vendor(project, name, phone=""):
    """Create a vendor and their accounts."""
    vendor = Vendor(project=project, name=name, phone=phone)
    # Temporarily set dummy accounts so we can get the count
    payable_account, advance_account = create_vendor_accounts(project, vendor)
    vendor.payable_account = payable_account
    vendor.advance_account = advance_account
    vendor.save()
    return vendor
