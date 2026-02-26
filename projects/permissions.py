"""
Project-level role-based permission helpers.

Role hierarchy:
  admin      — full access: all accounting operations + member management
  accountant — all accounting operations, cannot manage members
  viewer     — read-only: can view, cannot mutate anything
  None       — no membership: no access at all

These functions are the single source of truth for authorization.
All service functions call the `assert_*` helpers so that business
logic remains enforced even when accessed outside the Django view
layer (e.g. a future REST/React API).
"""
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.shortcuts import redirect


def get_role(user, project):
    """Return the user's role string for this project, or None if not a member."""
    if user.is_superuser:
        return "admin"
    from projects.models import ProjectMember
    try:
        return ProjectMember.objects.get(project=project, user=user).role
    except ProjectMember.DoesNotExist:
        return None


# ── Assertion helpers (for services) ────────────────────────────────────────

def assert_can_do_accounting(user, project):
    """
    Raise PermissionDenied if the user cannot perform accounting/mutation operations.
    Allowed roles: admin, accountant.
    """
    role = get_role(user, project)
    if role not in ("admin", "accountant"):
        raise PermissionDenied(
            "You do not have permission to perform accounting operations on this project."
        )


def assert_is_project_admin(user, project):
    """
    Raise PermissionDenied if the user is not a project admin.
    Only admins can manage project members.
    """
    role = get_role(user, project)
    if role != "admin":
        raise PermissionDenied("Only project admins can perform this action.")


# ── View helpers (for Django views) ─────────────────────────────────────────
# Return None on success, or a redirect Response on denial.

def require_accounting(request, project):
    """
    View guard: redirect with an error message if the user cannot do accounting.
    Usage::
        denied = require_accounting(request, project)
        if denied:
            return denied
    """
    try:
        assert_can_do_accounting(request.user, project)
        return None
    except PermissionDenied as exc:
        messages.error(request, str(exc))
        return redirect("projects:dashboard", pk=project.pk)


def require_admin(request, project):
    """
    View guard: redirect with an error message if the user is not a project admin.
    """
    try:
        assert_is_project_admin(request.user, project)
        return None
    except PermissionDenied as exc:
        messages.error(request, str(exc))
        return redirect("projects:dashboard", pk=project.pk)
