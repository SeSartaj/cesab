"""Project services."""
from django.db import transaction as db_transaction
from .models import Project
from coa.services import create_standard_coa


@db_transaction.atomic
def create_project(name, base_currency, description="", start_date=None):
    """Create a project and its standard chart of accounts."""
    project = Project.objects.create(
        name=name,
        base_currency=base_currency,
        description=description,
        start_date=start_date,
    )
    create_standard_coa(project)
    return project
