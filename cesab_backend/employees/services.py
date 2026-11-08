"""Employee services."""
from django.db import transaction as db_transaction
from .models import ProjectEmployee
from coa.services import create_employee_accounts
from projects.permissions import assert_can_do_accounting


@db_transaction.atomic
def create_employee(project, user, name, salary_type, salary_amount):
    """Create an employee and their accounts. Requires accounting permission."""
    assert_can_do_accounting(user, project)
    employee = ProjectEmployee(
        project=project, name=name, salary_type=salary_type, salary_amount=salary_amount
    )
    expense_account, payable_account = create_employee_accounts(project, employee)
    employee.expense_account = expense_account
    employee.payable_account = payable_account
    employee.save()
    return employee
