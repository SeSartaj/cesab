"""Contact services."""
from django.db import transaction as db_transaction
from .models import Contact
from coa.services import create_contact_accounts


@db_transaction.atomic
def create_contact(project, name, phone="", contact_type=Contact.VENDOR):
    """Create a contact and their ledger accounts based on contact_type."""
    contact = Contact(project=project, name=name, phone=phone, contact_type=contact_type)
    create_contact_accounts(project, contact)
    contact.save()
    return contact


# Backward-compat alias
def create_vendor(project, name, phone=""):
    return create_contact(project, name, phone, Contact.VENDOR)
