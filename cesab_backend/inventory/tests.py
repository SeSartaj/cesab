from datetime import date
from decimal import Decimal

from django.test import TestCase

from auth_users.models import User
from coa.models import Account
from coa.services import create_standard_coa
from core.models import Currency
from documents.models import POSTED, VendorBill
from inventory.models import InventoryMovement
from inventory.services import create_inventory_item, record_inventory_purchase_on_credit
from projects.models import Project
from vendors.models import Contact


def _make_currency(code, name="", symbol=""):
    currency, _ = Currency.objects.get_or_create(
        code=code,
        defaults={"name": name or code, "symbol": symbol, "is_active": True},
    )
    return currency


def _make_user(username="tester"):
    user, _ = User.objects.get_or_create(username=username)
    return user


def _make_project(base_currency, name="Inventory Project"):
    project = Project.objects.create(name=name, base_currency=base_currency)
    create_standard_coa(project)
    return project


def _make_vendor(project, name="ACME Vendor"):
    contact = Contact.objects.create(
        project=project,
        name=name,
        contact_type=Contact.VENDOR,
    )
    payable_parent = Account.objects.filter(project=project, code="2100").first()
    advance_parent = Account.objects.filter(project=project, code="1300").first()
    contact.payable_account = Account.objects.create(
        project=project,
        code=f"2101-{name[:4]}",
        name=f"Payable - {name}",
        account_type="liability",
        parent=payable_parent,
    )
    contact.advance_account = Account.objects.create(
        project=project,
        code=f"1301-{name[:4]}",
        name=f"Advance - {name}",
        account_type="asset",
        parent=advance_parent,
    )
    contact.save()
    return contact


class InventoryCreditPurchaseTests(TestCase):
    def setUp(self):
        self.base_currency = _make_currency("AFN")
        self.project = _make_project(self.base_currency)
        self.user = _make_user()
        self.vendor = _make_vendor(self.project)
        self.item = create_inventory_item(
            project=self.project,
            name="Cement",
            unit="bag",
        )

    def test_credit_purchase_creates_posted_vendor_bill(self):
        journal_entry = record_inventory_purchase_on_credit(
            project=self.project,
            user=self.user,
            date=date(2026, 4, 4),
            item=self.item,
            quantity=Decimal("10"),
            unit_cost=Decimal("25.50"),
            vendor=self.vendor,
            description="Credit purchase of cement",
            currency=self.base_currency,
            exchange_rate=Decimal("1"),
        )

        movement = InventoryMovement.objects.get(journal_entry=journal_entry)
        bill = VendorBill.objects.get(journal_entry=journal_entry)

        self.assertEqual(movement.total_cost, Decimal("255.00"))
        self.assertEqual(bill.contact, self.vendor)
        self.assertEqual(bill.status, POSTED)
        self.assertEqual(bill.notes, "Credit purchase of cement")
        self.assertEqual(bill.total_amount(), Decimal("255.00"))
        self.assertEqual(bill.lines.count(), 1)

        line = bill.lines.get()
        self.assertEqual(line.account, self.item.inventory_account)
        self.assertEqual(line.quantity, Decimal("10.0000"))
        self.assertEqual(line.unit_price, Decimal("25.50"))

        payable_line = journal_entry.lines.get(account=self.vendor.payable_account)
        inventory_line = journal_entry.lines.get(account=self.item.inventory_account)
        self.assertEqual(payable_line.credit, Decimal("255.00"))
        self.assertEqual(inventory_line.debit, Decimal("255.00"))