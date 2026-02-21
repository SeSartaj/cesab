# CESAB Construction Finance Management System

A project-level finance management system for CESAB Construction, built with Django. Designed for multi-currency, multi-partner Islamic construction project accounting following ACCA standards.

---

## Features

- **Project Management** – Create and manage construction projects with base currency
- **Partner & Equity Tracking** – Add shareholders, track capital commitments and ownership percentages
- **Chart of Accounts (COA)** – Auto-generated double-entry COA per project (Assets, Liabilities, Equity, Income, Expenses)
- **12 Transaction Types** – Capital Contribution, Shareholder Withdrawal, Vendor Bill, Vendor Advance, Vendor Payment, Cash Expense, Cashbox Transfer, Bank Deposit, Project Income, Asset Purchase, Pay Salary, Manual Journal Entry
- **Multi-Currency** – Supports AFN, USD, EUR, IRR, PKR, AED with exchange-rate tracking
- **Journal & Audit Trail** – Full double-entry journal with line-level detail
- **Role-Based Access** – Admin, Accountant (read-write), Viewer (read-only)
- **Bilingual** – English and Persian (Dari/Farsi) with RTL support

---

## Requirements

- Python 3.12+
- See `requirements.txt` for all Python packages

---

## Installation

```bash
# Clone or copy the project to your server
cd /path/to/cesab

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env .env.local   # edit SECRET_KEY and ALLOWED_HOSTS for production

# Apply migrations
python manage.py migrate

# Load initial data (currencies + default users)
python manage.py shell -c "
from core.models import Currency
currencies = [
    ('AFN', 'Afghan Afghani', 'Af'),
    ('USD', 'US Dollar', '\$'),
    ('EUR', 'Euro', '€'),
    ('IRR', 'Iranian Rial', '﷼'),
    ('PKR', 'Pakistani Rupee', '₨'),
    ('AED', 'UAE Dirham', 'د.إ'),
]
for code, name, symbol in currencies:
    Currency.objects.get_or_create(code=code, defaults={'name': name, 'symbol': symbol})
print('Currencies created.')
"

python manage.py shell -c "
from auth_users.models import User
User.objects.create_superuser('admin', '', 'cesab@2024', role='admin')
User.objects.create_user('accountant', '', 'cesab@2024', role='accountant')
User.objects.create_user('viewer', '', 'cesab@2024', role='viewer')
print('Users created.')
"

# Compile translations
python manage.py compilemessages

# Run development server
python manage.py runserver
```

---

## Default Login Credentials

| Username    | Password     | Role        | Access               |
|-------------|--------------|-------------|----------------------|
| admin       | cesab@2024   | Admin       | Full access          |
| accountant  | cesab@2024   | Accountant  | Record transactions  |
| viewer      | cesab@2024   | Viewer      | View only            |

> **Important:** Change all passwords before going live.

---

## Usage Guide

### 1. Create a Project
- Log in as admin
- Go to **Projects → New Project**
- Enter name, base currency, and start date

### 2. Set Up Chart of Accounts
- Navigate to the project dashboard
- Click **Chart of Accounts** in the sidebar
- The system auto-generates standard accounts when you add partners, cashboxes, vendors, and employees

### 3. Add Shareholders (Partners)
- From the project dashboard → **Shareholders → Add Shareholder**
- Enter name, phone, ownership %, capital commitment, and join date
- The system creates Capital and Current accounts for the partner automatically

### 4. Add Cashboxes
- **Cashboxes → Add Cashbox**
- Specify name and currency
- The system creates an asset account for the cashbox

### 5. Record Transactions
- From the dashboard, click any of the 12 transaction tiles
- Fill in the form and submit
- A double-entry journal entry is created automatically

### 6. View Journal
- **Journal** in the sidebar – filter by date range and transaction type
- Click any entry to see full debit/credit lines

### 7. Switch Language
- Click **FA** / **EN** in the top navigation bar to switch between English and Persian

---

## Transaction Types Reference

| Transaction | Dr | Cr |
|---|---|---|
| Capital Contribution | Cashbox | Partner Capital |
| Shareholder Withdrawal | Partner Current | Cashbox |
| Vendor Bill | Expense | Vendor Payable |
| Vendor Advance | Vendor Advance | Cashbox |
| Vendor Payment | Vendor Payable | Cashbox |
| Cash Expense | Expense | Cashbox |
| Cashbox Transfer | To Cashbox | From Cashbox |
| Bank Deposit | Bank Cashbox | From Cashbox |
| Project Income | Cashbox | Income |
| Asset Purchase | Asset | Cashbox |
| Pay Salary | Salary Expense | Cashbox |
| Manual Journal Entry | User-defined | User-defined |

---

## File Structure

```
cesab/
├── config/           # Django settings, URLs, context processors
├── auth_users/       # Custom user model (admin/accountant/viewer)
├── core/             # Currency model, shared base
├── projects/         # Project model, dashboard
├── partners/         # Shareholder/partner management
├── cash/             # Cashbox management
├── coa/              # Chart of Accounts
├── journal/          # Journal entries and lines
├── vendors/          # Vendor management
├── employees/        # Employee management
├── transactions/     # All 12 transaction type views/forms/services
├── templates/        # HTML templates (Bootstrap 5 + RTL)
├── locale/           # Translation files (fa/Persian)
├── .env              # Environment configuration
├── requirements.txt  # Python dependencies
└── db.sqlite3        # SQLite database (development)
```

---

## Production Checklist

- [ ] Set `DEBUG=False` in `.env`
- [ ] Set a strong `SECRET_KEY` in `.env`
- [ ] Add your server domain to `ALLOWED_HOSTS`
- [ ] Use PostgreSQL instead of SQLite (update `DATABASES` in `config/settings.py`)
- [ ] Configure a proper web server (Nginx + Gunicorn)
- [ ] Set up static file serving: `python manage.py collectstatic`
- [ ] Change all default passwords

---

## Technology Stack

- **Backend:** Django 6.0, Python 3.12
- **Database:** SQLite (development) / PostgreSQL (production recommended)
- **Frontend:** Bootstrap 5, Bootstrap Icons (CDN)
- **i18n:** Django gettext, Persian (Dari/Farsi) translation included
- **Auth:** Custom User model with role-based permissions
