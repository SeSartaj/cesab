# CESAB: Construction Finance Management System
this Fianancial management system will follow Standards based on the ACCA curricula. It 
is a project based finance management system. each project will have a base currencly and 
all the transaction will happen in that currency. however, some transactions may be done
in other currencies, for that it should be tracked, which currency was used and exchange rate
to the base currency at that time. this system is in islamic country, so no interest (riba), insurance in it.



# Architecture
- all business logic must be in services folders. this way, the whole business logic can be unit-tested, and I can easily swap frontend and use react in the future
- support english and persian switching. 
- the UI must be minimal and simple, follow HCI 10 heuristics. 

## user friendly by design
most users do not know accounting principles, so the system provides common transaction types
to guide data entry and reduce mistakes.

### common transaction types
- shareholder capital contribution
- shareholder withdrawal / distribution
- vendor bill (expense on credit)
- vendor advance payment
- vendor payment against bill
- cash expense (paid from cashbox)
- cashbox to cashbox transfer
- bank deposit / cash withdrawal
- project income (service revenue)
- asset purchase (equipment, tools)
- pay salary


# common consideractions
- when a project is created, automatically create chart of accounts for it with standard chart of acounts
- when a partner is added, create accounts in chart of accounts for it
- when a vendor is added, create accounts in chart of accounts for it.
- if a user with only read permissions enter the system, they must not see the actions which he's not supposed to do. 


# UX/UI
- support localization
- each project should have one header that will allow user to navigate. 
- default page of project must show all transaction types a user can make, and a summary report 
- it must also show contribution, how much remaining of each partner. 
- it should also show expenses, and how much in each cashbox. 
- don't ask for optional fields from user. 
- each model should have its own list page, detail page which have edit button. 
- for adding journal entry, it must have option to add multiple lines. make sure the sum of debit and credit in journal entry is balanced.
- for each transaction type, there should be a page that shows list of all transactions of that type. 

the url structure should be like this:
- /projects/ - list of projects
- /projects/1/ project dashboard
- /projects/1/shareholders: shareholders of the project
- /projects/1/cashboxes: cashboxes of the project, etc. 





# Django Apps Structure

```
core/
    Currency

auth_users/
    User

partners/
    Partner
    ProjectPartner

projects/
    Project

coa/
    Account

cash/
    Cashbox

journal/
    JournalEntry
    JournalLine

vendors/
    Vendor

employees/
    ProjectEmployee
```

---

# core app

## Currency

```
class Currency(models.Model):
    code = models.CharField(max_length=3, unique=True)
    name = models.CharField(max_length=50)
    symbol = models.CharField(max_length=5, blank=True)

    decimal_places = models.IntegerField(default=2)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.code
```

---

# auth_user app

## User (extends AbstractUser)

Each user belongs to a Partner.

```
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.username
```

---

# partners app

## Partner

```
class Partner(models.Model):
    name = models.CharField(max_length=200)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)

    # Optional link to system user
    user = models.ForeignKey(
        "auth_users.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        help_text="Optional user account for this partner"
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
```

---

## ProjectPartner

Represents partner participation in a project.

```
class ProjectPartner(models.Model):

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="project_partners"
    )

    partner = models.ForeignKey(
        "partners.Partner",
        on_delete=models.PROTECT,
        related_name="project_participations"
    )

    ownership_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2
    )

    capital_commitment = models.DecimalField(
        max_digits=18,
        decimal_places=2
    )

    capital_account = models.ForeignKey(
        "coa.Account",
        on_delete=models.PROTECT,
        related_name="partner_capital_accounts"
    )

    current_account = models.ForeignKey(
        "coa.Account",
        on_delete=models.PROTECT,
        related_name="partner_current_accounts"
    )

    joined_at = models.DateField()

    exited_at = models.DateField(null=True, blank=True)

    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("project", "partner")

    def __str__(self):
        return f"{self.partner.name} - {self.project.name}"
```

---

# projects app

## Project

```
class Project(models.Model):

    name = models.CharField(max_length=200)

    base_currency = models.ForeignKey(
        "core.Currency",
        on_delete=models.PROTECT
    )

    created_at = models.DateTimeField(auto_now_add=True)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name
```

---

# coa app

## Account

Project-specific chart of accounts.

```
class Account(models.Model):

    ACCOUNT_TYPES = [
        ("asset", "Asset"),
        ("liability", "Liability"),
        ("equity", "Equity"),
        ("income", "Income"),
        ("expense", "Expense"),
    ]

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="accounts"
    )

    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="children"
    )

    name = models.CharField(max_length=200)

    code = models.CharField(max_length=20)

    account_type = models.CharField(
        max_length=20,
        choices=ACCOUNT_TYPES
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("project", "code")

    def __str__(self):
        return f"{self.code} - {self.name}"
```

---

# cash app

## Cashbox

Represents physical or bank account.

```
class Cashbox(models.Model):

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="cashboxes"
    )

    name = models.CharField(max_length=200)

    account = models.OneToOneField(
        "coa.Account",
        on_delete=models.CASCADE
    )

    currency = models.ForeignKey(
        "core.Currency",
        on_delete=models.PROTECT
    )

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name
```

---

# journal app

## JournalEntry

```
class JournalEntry(models.Model):

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="journal_entries"
    )

    date = models.DateField()

    description = models.TextField(blank=True)

    created_by = models.ForeignKey(
        "auth_users.User",
        on_delete=models.PROTECT
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"JE-{self.id}"
```

---

## JournalLine

```
class JournalLine(models.Model):

    journal_entry = models.ForeignKey(
        "journal.JournalEntry",
        on_delete=models.CASCADE,
        related_name="lines"
    )

    account = models.ForeignKey(
        "coa.Account",
        on_delete=models.PROTECT
    )

    debit = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0
    )

    credit = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0
    )

    transaction_currency = models.ForeignKey(
        "core.Currency",
        on_delete=models.PROTECT
    )

    exchange_rate = models.DecimalField(
        max_digits=18,
        decimal_places=6
    )

    debit_tc = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0
    )

    credit_tc = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0
    )
```

---

# vendors app

## Vendor

```
class Vendor(models.Model):

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="vendors"
    )

    name = models.CharField(max_length=200)

    phone = models.CharField(max_length=50, blank=True)

    payable_account = models.ForeignKey(
        "coa.Account",
        on_delete=models.PROTECT,
        related_name="vendor_payable_accounts"
    )

    advance_account = models.ForeignKey(
        "coa.Account",
        on_delete=models.PROTECT,
        related_name="vendor_advance_accounts"
    )

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name
```

---

# employees app

## ProjectEmployee

Supports both monthly and daily wage workers.

```
class ProjectEmployee(models.Model):

    SALARY_TYPES = [
        ("monthly", "Monthly"),
        ("daily", "Daily"),
    ]

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="employees"
    )

    name = models.CharField(max_length=200)

    salary_type = models.CharField(
        max_length=20,
        choices=SALARY_TYPES
    )

    salary_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2
    )

    expense_account = models.ForeignKey(
        "coa.Account",
        on_delete=models.PROTECT,
        related_name="employee_expense_accounts"
    )

    payable_account = models.ForeignKey(
        "coa.Account",
        on_delete=models.PROTECT,
        related_name="employee_payable_accounts"
    )

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name
```

---

