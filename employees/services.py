"""Employee services."""
from django.db import transaction as db_transaction
from .models import ProjectEmployee
from coa.services import create_employee_accounts


@db_transaction.atomic
def create_employee(project, name, salary_type, salary_amount):
    """Create an employee and their accounts."""
    employee = ProjectEmployee(
        project=project, name=name, salary_type=salary_type, salary_amount=salary_amount
    )
    expense_account, payable_account = create_employee_accounts(project, employee)
    employee.expense_account = expense_account
    employee.payable_account = payable_account
    employee.save()
    return employee
