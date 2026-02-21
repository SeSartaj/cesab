"""Partner services."""
from django.db import transaction as db_transaction
from .models import Partner, ProjectPartner
from coa.services import create_partner_accounts


@db_transaction.atomic
def add_partner_to_project(project, partner, ownership_percent, capital_commitment, joined_at):
    """Add a partner to a project and create their accounts."""
    capital_account, current_account = create_partner_accounts(project, partner)
    pp = ProjectPartner.objects.create(
        project=project,
        partner=partner,
        ownership_percent=ownership_percent,
        capital_commitment=capital_commitment,
        capital_account=capital_account,
        current_account=current_account,
        joined_at=joined_at,
    )
    return pp
