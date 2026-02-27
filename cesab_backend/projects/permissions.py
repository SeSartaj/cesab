"""
Role → permission mapping and guardian helpers for project-level access control.

Roles and what they grant on a specific Project object:
  admin      – full control: view, edit project, manage members, add financial data
  accountant – can view the project and add/edit financial data
  viewer     – read-only access to the project

To add a new role in the future:
  1. Add the role constant + choice to ProjectMember.ROLE_CHOICES
  2. Add its permission list here in ROLE_PERMISSIONS
  3. Run makemigrations (choices change triggers a migration)
"""

from guardian.shortcuts import assign_perm, remove_perm

# Maps each role to the list of *codenames* (without app label)
# defined in Project.Meta.permissions plus Django's built-in model perms.
ROLE_PERMISSIONS: dict[str, list[str]] = {
    "admin": [
        "view_project",        # see the project
        "change_project",      # edit project settings
        "manage_members",      # add / change / remove project members
        "add_financial_data",  # create journal entries, cashboxes, etc.
    ],
    "accountant": [
        "view_project",
        "add_financial_data",
    ],
    "viewer": [
        "view_project",
    ],
}

# Union of every permission that this system can assign.
_ALL_MANAGED_PERMISSIONS: frozenset[str] = frozenset(
    perm
    for perms in ROLE_PERMISSIONS.values()
    for perm in perms
)


def assign_role_permissions(user, project, role: str) -> None:
    """
    Assign guardian object permissions for *role* to *user* on *project*.
    Any previously assigned managed permissions are revoked first so the
    user ends up with exactly the permissions their role requires.
    """
    revoke_all_permissions(user, project)
    for perm in ROLE_PERMISSIONS.get(role, []):
        assign_perm(perm, user, project)


def revoke_all_permissions(user, project) -> None:
    """Remove every managed project permission for *user* on *project*."""
    for perm in _ALL_MANAGED_PERMISSIONS:
        remove_perm(perm, user, project)


def can_access_financial(user, project) -> bool:
    """Return True if *user* may add/edit financial data in *project*.

    This is the single check that should be used across all sub-apps
    (cash, vendors, employees, partners, transactions, journal, inventory)
    to gate write operations.  Superusers always pass.
    """
    if user.is_superuser:
        return True
    return user.has_perm("projects.add_financial_data", project)
