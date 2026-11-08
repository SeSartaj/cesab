"""Project services."""
from django.db import transaction as db_transaction
from .models import Project, ProjectMember
from .permissions import assert_is_project_admin
from coa.services import create_standard_coa


@db_transaction.atomic
def create_project(name, base_currency, description="", start_date=None, created_by=None):
    """Create a project and its standard chart of accounts.

    If `created_by` is provided, that user is added as the project admin.
    """
    project = Project.objects.create(
        name=name,
        base_currency=base_currency,
        description=description,
        start_date=start_date,
    )
    create_standard_coa(project)
    if created_by is not None:
        ProjectMember.objects.create(project=project, user=created_by, role="admin")
    return project


def add_member(project, requesting_user, target_user, role):
    """
    Add *target_user* to *project* with the given role.
    Only project admins can invite members.
    Roles that can be assigned: 'accountant', 'viewer' (never 'admin' via invitation).
    Returns (ProjectMember, created: bool).
    """
    assert_is_project_admin(requesting_user, project)
    if role not in ("accountant", "viewer"):
        role = "viewer"
    pm, created = ProjectMember.objects.get_or_create(
        project=project,
        user=target_user,
        defaults={"role": role},
    )
    return pm, created


def remove_member(project, requesting_user, member):
    """
    Remove *member* from *project*.
    Only project admins can remove members.
    Admins cannot be removed, and a user cannot remove themselves.
    """
    assert_is_project_admin(requesting_user, project)
    if member.role == "admin":
        raise ValueError("Admin members cannot be removed.")
    if member.user == requesting_user:
        raise ValueError("You cannot remove yourself from the project.")
    member.delete()
