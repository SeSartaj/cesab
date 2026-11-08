"""Partner services."""
from django.db import transaction as db_transaction
from .models import ProjectPartner
from coa.services import create_partner_accounts
from projects.permissions import assert_can_do_accounting


@db_transaction.atomic
def add_partner_to_project(project, requesting_user, name, ownership_percent,
                           capital_commitment, joined_at, user=None):
    """Add a partner to a project and create their accounts. Requires accounting permission.
    
    `requesting_user` is the staff user performing the action.
    `user` (optional) is the system user account linked to this partner.
    """
    assert_can_do_accounting(requesting_user, project)
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
