"""
Tests for the vendors app — Contact model and create_contact service.
"""
from django.test import TestCase

from coa.services import create_standard_coa
from core.models import Currency
from projects.models import Project
from auth_users.models import User
from vendors.models import Contact
from vendors.services import create_contact, create_vendor


def _make_currency(code):
    c, _ = Currency.objects.get_or_create(
        code=code, defaults={"name": code, "symbol": "", "is_active": True}
    )
    return c


def _make_project(base_currency):
    proj = Project.objects.create(
        name="VendorTestProject",
        base_currency=base_currency,
    )
    create_standard_coa(proj)
    return proj


class ContactTypeTests(TestCase):

    def setUp(self):
        base = _make_currency("AFN")
        self.project = _make_project(base)

    def test_vendor_is_vendor(self):
        c = Contact(project=self.project, name="V", contact_type=Contact.VENDOR)
        self.assertTrue(c.is_vendor)
        self.assertFalse(c.is_customer)

    def test_customer_is_customer(self):
        c = Contact(project=self.project, name="C", contact_type=Contact.CUSTOMER)
        self.assertFalse(c.is_vendor)
        self.assertTrue(c.is_customer)

    def test_both_is_vendor_and_customer(self):
        c = Contact(project=self.project, name="B", contact_type=Contact.BOTH)
        self.assertTrue(c.is_vendor)
        self.assertTrue(c.is_customer)

    def test_str_representation(self):
        c = Contact(name="ACME", contact_type=Contact.VENDOR)
        self.assertEqual(str(c), "ACME")


class CreateContactServiceTests(TestCase):

    def setUp(self):
        base = _make_currency("AFN")
        self.project = _make_project(base)

    def test_create_vendor_gets_payable_and_advance(self):
        contact = create_contact(self.project, "ACME", contact_type=Contact.VENDOR)
        self.assertIsNotNone(contact.pk)
        self.assertIsNotNone(contact.payable_account)
        self.assertIsNotNone(contact.advance_account)
        self.assertIsNone(contact.receivable_account)

    def test_create_customer_gets_receivable(self):
        contact = create_contact(self.project, "ClientCo", contact_type=Contact.CUSTOMER)
        self.assertIsNotNone(contact.receivable_account)
        self.assertIsNone(contact.payable_account)
        self.assertIsNone(contact.advance_account)

    def test_create_both_gets_all_accounts(self):
        contact = create_contact(self.project, "Both Inc", contact_type=Contact.BOTH)
        self.assertIsNotNone(contact.payable_account)
        self.assertIsNotNone(contact.advance_account)
        self.assertIsNotNone(contact.receivable_account)

    def test_create_vendor_alias(self):
        """create_vendor() is a backward-compat wrapper."""
        contact = create_vendor(self.project, "LegacyVendor")
        self.assertEqual(contact.contact_type, Contact.VENDOR)
        self.assertIsNotNone(contact.payable_account)
