"""
Management command: python manage.py initdata

Seeds the database with:
  1. Currencies          — AFN (base), USD
  2. Django Groups       — Accountant, Viewer  (with appropriate permissions)
  3. Superuser           — created interactively if none exists

Safe to run multiple times — uses get_or_create throughout.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import transaction


CURRENCIES = [
    # code,  name,                   symbol, decimal_places, is_base
    ("AFN",  "Afghan Afghani",       "؋",    2),
    ("USD",  "US Dollar",            "$",    2),
]

# Permissions granted to the Accountant group
# Format: "app_label.codename"
ACCOUNTANT_PERMISSIONS = [
    # Journal
    "journal.add_journalentry",
    "journal.view_journalentry",
    # Transactions (no model of their own, covered by journal)
    # COA — view only, system creates accounts automatically
    "coa.view_account",
    # Cash
    "cash.add_cashbox",
    "cash.change_cashbox",
    "cash.view_cashbox",
    # Partners
    "partners.view_projectpartner",
    # Vendors
    "vendors.add_vendor",
    "vendors.change_vendor",
    "vendors.view_vendor",
    # Employees
    "employees.add_projectemployee",
    "employees.change_projectemployee",
    "employees.view_projectemployee",
    # Inventory
    "inventory.add_inventoryitem",
    "inventory.change_inventoryitem",
    "inventory.view_inventoryitem",
    "inventory.add_inventorymovement",
    "inventory.view_inventorymovement",
    # Projects — view only (superuser creates projects)
    "projects.view_project",
    "projects.view_projectmember",
]

# Viewer gets view-only permissions across all relevant models
VIEWER_PERMISSIONS = [p for p in ACCOUNTANT_PERMISSIONS if p.split(".")[1].startswith("view_")]


class Command(BaseCommand):
    help = "Seed initial data: currencies, groups, and optional superuser."

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-superuser",
            action="store_true",
            help="Skip the superuser creation prompt.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        self._seed_currencies()
        self._seed_groups()
        if not options["no_superuser"]:
            self._seed_superuser()
        self.stdout.write(self.style.SUCCESS("\n✔  initdata complete."))

    # ------------------------------------------------------------------
    def _seed_currencies(self):
        from core.models import Currency
        self.stdout.write("\n── Currencies ──")
        for code, name, symbol, dp in CURRENCIES:
            obj, created = Currency.objects.get_or_create(
                code=code,
                defaults={"name": name, "symbol": symbol, "decimal_places": dp, "is_active": True},
            )
            status = "created" if created else "exists "
            self.stdout.write(f"  [{status}] {code}  {name}")

    # ------------------------------------------------------------------
    def _seed_groups(self):
        self.stdout.write("\n── Groups & Permissions ──")
        self._create_group("Accountant", ACCOUNTANT_PERMISSIONS)
        self._create_group("Viewer",     VIEWER_PERMISSIONS)

    def _create_group(self, name, permission_strings):
        group, created = Group.objects.get_or_create(name=name)
        status = "created" if created else "exists "
        self.stdout.write(f"  [{status}] Group: {name}")

        perms_added = 0
        perms_missing = []
        for perm_str in permission_strings:
            app_label, codename = perm_str.split(".")
            try:
                perm = Permission.objects.get(
                    codename=codename,
                    content_type__app_label=app_label,
                )
                group.permissions.add(perm)
                perms_added += 1
            except Permission.DoesNotExist:
                perms_missing.append(perm_str)

        self.stdout.write(f"           → {perms_added} permissions assigned")
        for p in perms_missing:
            self.stdout.write(self.style.WARNING(f"           ⚠  permission not found (run migrate first?): {p}"))

    # ------------------------------------------------------------------
    def _seed_superuser(self):
        User = get_user_model()
        self.stdout.write("\n── Superuser ──")
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write("  [exists ] A superuser already exists — skipping.")
            return

        self.stdout.write("  No superuser found. Creating one now.")
        username = input("  Username [admin]: ").strip() or "admin"
        email    = input("  Email    []:      ").strip()
        password = None
        while not password:
            import getpass
            password = getpass.getpass("  Password:         ")
            confirm  = getpass.getpass("  Confirm password: ")
            if password != confirm:
                self.stdout.write(self.style.ERROR("  Passwords do not match. Try again."))
                password = None

        User.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write(self.style.SUCCESS(f"  [created] Superuser '{username}' created."))
