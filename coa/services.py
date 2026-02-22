"""Chart of Accounts services - business logic for account management."""
from .models import Account

STANDARD_COA = [
    {"code": "1000", "name": "Assets", "type": "asset", "parent_code": None},
    {"code": "1100", "name": "Cash & Bank", "type": "asset", "parent_code": "1000"},
    {"code": "1200", "name": "Accounts Receivable", "type": "asset", "parent_code": "1000"},
    {"code": "1300", "name": "Vendor Advances", "type": "asset", "parent_code": "1000"},
    {"code": "1400", "name": "Fixed Assets", "type": "asset", "parent_code": "1000"},
    {"code": "1500", "name": "Inventory", "type": "asset", "parent_code": "1000"},
    {"code": "1600", "name": "Other Assets", "type": "asset", "parent_code": "1000"},
    {"code": "2000", "name": "Liabilities", "type": "liability", "parent_code": None},
    {"code": "2100", "name": "Accounts Payable", "type": "liability", "parent_code": "2000"},
    {"code": "2200", "name": "Salaries Payable", "type": "liability", "parent_code": "2000"},
    {"code": "2300", "name": "Other Liabilities", "type": "liability", "parent_code": "2000"},
    {"code": "3000", "name": "Equity", "type": "equity", "parent_code": None},
    {"code": "3100", "name": "Partner Capital", "type": "equity", "parent_code": "3000"},
    {"code": "3200", "name": "Partner Current Accounts", "type": "equity", "parent_code": "3000"},
    {"code": "3300", "name": "Retained Earnings", "type": "equity", "parent_code": "3000"},
    {"code": "4000", "name": "Income", "type": "income", "parent_code": None},
    {"code": "4100", "name": "Project Revenue", "type": "income", "parent_code": "4000"},
    {"code": "4200", "name": "FX Gain", "type": "income", "parent_code": "4000"},
    {"code": "5000", "name": "Expenses", "type": "expense", "parent_code": None},
    {"code": "5100", "name": "Direct Costs", "type": "expense", "parent_code": "5000"},
    {"code": "5200", "name": "Salaries & Wages", "type": "expense", "parent_code": "5000"},
    {"code": "5300", "name": "General & Administrative", "type": "expense", "parent_code": "5000"},
    {"code": "5400", "name": "Asset Expenses", "type": "expense", "parent_code": "5000"},
    {"code": "5500", "name": "Inventory Expense", "type": "expense", "parent_code": "5000"},
    {"code": "5600", "name": "FX Loss", "type": "expense", "parent_code": "5000"},
]


def create_standard_coa(project):
    """Create standard chart of accounts for a new project."""
    accounts = {}
    for entry in STANDARD_COA:
        parent = accounts.get(entry["parent_code"]) if entry["parent_code"] else None
        account = Account.objects.create(
            project=project,
            code=entry["code"],
            name=entry["name"],
            account_type=entry["type"],
            parent=parent,
            is_system=True,
        )
        accounts[entry["code"]] = account
    return accounts


def get_or_create_fx_accounts(project):
    """
    Return (fx_gain_account, fx_loss_account) for the project.
    Creates them if they don't exist yet (needed for projects created before
    FX accounts were added to the standard COA).
    """
    gain_parent = Account.objects.filter(project=project, code="4000").first()
    loss_parent = Account.objects.filter(project=project, code="5000").first()
    gain_acc, _ = Account.objects.get_or_create(
        project=project,
        code="4200",
        defaults={
            "name": "FX Gain",
            "account_type": "income",
            "parent": gain_parent,
            "is_system": True,
        },
    )
    loss_acc, _ = Account.objects.get_or_create(
        project=project,
        code="5600",
        defaults={
            "name": "FX Loss",
            "account_type": "expense",
            "parent": loss_parent,
            "is_system": True,
        },
    )
    return gain_acc, loss_acc


def _next_code(project, prefix, start=1):
    """Find next available code with prefix."""
    i = start
    while True:
        code = f"{prefix}{i:02d}"
        if not Account.objects.filter(project=project, code=code).exists():
            return code
        i += 1


def create_partner_accounts(project, partner):
    """Create capital and current accounts for a new partner."""
    idx = project.project_partners.count() + 1
    cap_code = _next_code(project, "31", idx)
    cur_code = _next_code(project, "32", idx)

    capital_account = Account.objects.create(
        project=project,
        code=cap_code,
        name=f"{partner.name} - Capital",
        account_type="equity",
        parent=Account.objects.filter(project=project, code="3100").first(),
        is_system=True,
    )
    current_account = Account.objects.create(
        project=project,
        code=cur_code,
        name=f"{partner.name} - Current Account",
        account_type="equity",
        parent=Account.objects.filter(project=project, code="3200").first(),
        is_system=True,
    )
    return capital_account, current_account


def create_vendor_accounts(project, vendor):
    """Create payable and advance accounts for a new vendor."""
    idx = project.vendors.count() + 1
    pay_code = _next_code(project, "21", idx)
    adv_code = _next_code(project, "13", idx)

    payable_account = Account.objects.create(
        project=project,
        code=pay_code,
        name=f"{vendor.name} - Payable",
        account_type="liability",
        parent=Account.objects.filter(project=project, code="2100").first(),
        is_system=True,
    )
    advance_account = Account.objects.create(
        project=project,
        code=adv_code,
        name=f"{vendor.name} - Advance",
        account_type="asset",
        parent=Account.objects.filter(project=project, code="1300").first(),
        is_system=True,
    )
    return payable_account, advance_account


def create_employee_accounts(project, employee):
    """Create expense and payable accounts for a new employee."""
    idx = project.employees.count() + 1
    exp_code = _next_code(project, "52", idx)
    pay_code = _next_code(project, "22", idx)

    expense_account = Account.objects.create(
        project=project,
        code=exp_code,
        name=f"{employee.name} - Salary Expense",
        account_type="expense",
        parent=Account.objects.filter(project=project, code="5200").first(),
        is_system=True,
    )
    payable_account = Account.objects.create(
        project=project,
        code=pay_code,
        name=f"{employee.name} - Salary Payable",
        account_type="liability",
        parent=Account.objects.filter(project=project, code="2200").first(),
        is_system=True,
    )
    return expense_account, payable_account


def create_cashbox_account(project, cashbox):
    """Create asset account for a new cashbox."""
    idx = project.cashboxes.count() + 1
    code = _next_code(project, "11", idx)

    account = Account.objects.create(
        project=project,
        code=code,
        name=cashbox.name,
        account_type="asset",
        parent=Account.objects.filter(project=project, code="1100").first(),
        is_system=True,
    )
    return account


def create_inventory_accounts(project, item_name):
    """Create inventory asset and expense accounts for a new inventory item."""
    idx = project.inventory_items.count() + 1
    inv_code = _next_code(project, "15", idx)
    exp_code = _next_code(project, "55", idx)

    inventory_account = Account.objects.create(
        project=project,
        code=inv_code,
        name=f"{item_name} — Inventory",
        account_type="asset",
        parent=Account.objects.filter(project=project, code="1500").first(),
        is_system=True,
    )
    expense_account = Account.objects.create(
        project=project,
        code=exp_code,
        name=f"{item_name} — Expense",
        account_type="expense",
        parent=Account.objects.filter(project=project, code="5500").first(),
        is_system=True,
    )
    return inventory_account, expense_account
