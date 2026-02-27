"""Partner services."""
from django.db import transaction as db_transaction
from .models import ProjectPartner
from coa.services import create_partner_accounts


@db_transaction.atomic
def add_partner_to_project(project, name, ownership_percent, capital_commitment, joined_at, user=None):
    """Add a partner to a project and create their accounts. User linkage is optional."""
    capital_account, current_account = create_partner_accounts(project, name)
    pp = ProjectPartner.objects.create(
        project=project,
        name=name,
        user=user,
        ownership_percent=ownership_percent,
        capital_commitment=capital_commitment,
        capital_account=capital_account,
        current_account=current_account,
        joined_at=joined_at,
    )
    return pp
