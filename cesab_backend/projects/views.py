"""Project views with guardian object-level permission enforcement."""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, CreateView, UpdateView
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.db.models import Q
from guardian.shortcuts import get_objects_for_user

from .models import Project, ProjectMember
from .services import create_project
from .forms import ProjectForm, ProjectMemberForm
from .permissions import assign_role_permissions, revoke_all_permissions
from partners.models import ProjectPartner
from cash.models import Cashbox
from journal.models import JournalEntry
from coa.models import Account


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _accessible_projects(user):
    """Return active projects visible to *user*.

    - Superusers see every active project.
    - Regular users see projects where guardian granted them ``view_project``
      OR where they are a linked ProjectPartner.
    """
    if user.is_superuser:
        return Project.objects.filter(is_active=True)

    member_qs = get_objects_for_user(
        user,
        "projects.view_project",
        klass=Project.objects.filter(is_active=True),
        accept_global_perms=False,
    )
    partner_pks = ProjectPartner.objects.filter(
        user=user, is_active=True
    ).values_list("project_id", flat=True)
    partner_qs = Project.objects.filter(is_active=True, pk__in=partner_pks)

    return (member_qs | partner_qs).distinct()


def _project_permission_ctx(user, project) -> dict:
    """Return a dict of boolean permission flags for use in templates."""
    if user.is_superuser:
        return {
            "can_edit": True,
            "can_manage_members": True,
            "can_add_financial": True,
        }
    return {
        "can_edit": user.has_perm("projects.change_project", project),
        "can_manage_members": user.has_perm("projects.manage_members", project),
        "can_add_financial": user.has_perm("projects.add_financial_data", project),
    }


def _require_project_access(user, project, perm="projects.view_project"):
    """Return True if *user* may access *project* with *perm*."""
    if user.is_superuser:
        return True
    if user.has_perm(perm, project):
        return True
    # Fall back: partner users always get read access
    if perm == "projects.view_project":
        return ProjectPartner.objects.filter(
            project=project, user=user, is_active=True
        ).exists()
    return False


# ---------------------------------------------------------------------------
# Project CRUD
# ---------------------------------------------------------------------------

class ProjectListView(LoginRequiredMixin, ListView):
    model = Project
    template_name = "projects/project_list.html"
    context_object_name = "projects"

    def get_queryset(self):
        return _accessible_projects(self.request.user)


class ProjectCreateView(LoginRequiredMixin, CreateView):
    form_class = ProjectForm
    template_name = "projects/project_form.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, _("Only the super admin can create projects."))
            return redirect("projects:list")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        data = form.cleaned_data
        project = create_project(
            name=data["name"],
            base_currency=data["base_currency"],
            description=data.get("description", ""),
            start_date=data.get("start_date"),
        )
        messages.success(self.request, _("Project created successfully."))
        return redirect("projects:dashboard", pk=project.pk)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = _("New Project")
        return ctx


class ProjectUpdateView(LoginRequiredMixin, UpdateView):
    model = Project
    form_class = ProjectForm
    template_name = "projects/project_form.html"

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if not request.user.is_authenticated:
            return response
        project = self.get_object()
        if not (request.user.is_superuser or request.user.has_perm("projects.change_project", project)):
            messages.error(request, _("You do not have permission to edit this project."))
            return redirect("projects:dashboard", pk=project.pk)
        return response

    def get_success_url(self):
        return reverse("projects:dashboard", kwargs={"pk": self.object.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = _("Edit Project")
        ctx["project"] = self.object
        return ctx


# ---------------------------------------------------------------------------
# Project dashboard
# ---------------------------------------------------------------------------

@login_required
def project_dashboard(request, pk):
    project = get_object_or_404(Project, pk=pk)

    if not _require_project_access(request.user, project):
        messages.error(request, _("You do not have access to this project."))
        return redirect("projects:list")

    user = request.user
    perm_ctx = _project_permission_ctx(user, project)

    # Partner summary
    partners = project.project_partners.filter(is_active=True).select_related(
        "user", "capital_account", "current_account"
    )
    partner_data = []
    for pp in partners:
        contributed = pp.contributed_amount()
        remaining = pp.capital_commitment - contributed
        if pp.capital_commitment > 0:
            percent_done = min(int((contributed / pp.capital_commitment) * 100), 100)
        else:
            percent_done = 0
        partner_data.append((pp, contributed, remaining, percent_done))

    # Cashbox balances
    cashboxes = project.cashboxes.filter(is_active=True).select_related("account", "currency")
    cashbox_data = [(cb, cb.balance()) for cb in cashboxes]

    # Income & Expense summary
    income_accounts = Account.objects.filter(project=project, account_type="income", is_active=True)
    expense_accounts = Account.objects.filter(project=project, account_type="expense", is_active=True)
    total_income = sum(a.balance() for a in income_accounts)
    total_expense = sum(a.balance() for a in expense_accounts)

    # Total payables
    liability_accounts = Account.objects.filter(project=project, account_type="liability", is_active=True)
    total_payables = sum(a.balance() for a in liability_accounts if a.balance() > 0)

    # Recent journal entries
    recent_entries = project.journal_entries.all()[:10]

    return render(request, "projects/dashboard.html", {
        "project": project,
        "partner_data": partner_data,
        "cashbox_data": cashbox_data,
        "total_income": total_income,
        "total_expense": total_expense,
        "net_profit": total_income - total_expense,
        "total_payables": total_payables,
        "recent_entries": recent_entries,
        **perm_ctx,
    })


# ---------------------------------------------------------------------------
# Member management (superuser or project admin only)
# ---------------------------------------------------------------------------

def _require_manage_members(request, project):
    """Return True if allowed; otherwise add an error message and return False."""
    if request.user.is_superuser:
        return True
    if request.user.has_perm("projects.manage_members", project):
        return True
    messages.error(request, _("You do not have permission to manage members."))
    return False


@login_required
def project_members(request, pk):
    """List all members of a project."""
    project = get_object_or_404(Project, pk=pk)
    if not _require_project_access(request.user, project):
        messages.error(request, _("You do not have access to this project."))
        return redirect("projects:list")

    members = project.members.select_related("user").order_by("role", "user__username")
    perm_ctx = _project_permission_ctx(request.user, project)

    return render(request, "projects/members.html", {
        "project": project,
        "members": members,
        **perm_ctx,
    })


@login_required
def add_member(request, pk):
    """Add a user to a project with a chosen role."""
    project = get_object_or_404(Project, pk=pk)
    if not _require_manage_members(request, project):
        return redirect("projects:members", pk=pk)

    if request.method == "POST":
        form = ProjectMemberForm(request.POST, project=project)
        if form.is_valid():
            member = form.save(commit=False)
            member.project = project
            member.save()  # save() triggers guardian perm assignment
            messages.success(request, _("%(user)s added as %(role)s.") % {
                "user": member.user,
                "role": member.get_role_display(),
            })
            return redirect("projects:members", pk=pk)
    else:
        form = ProjectMemberForm(project=project)

    return render(request, "projects/member_form.html", {
        "form": form,
        "project": project,
        "title": _("Add Member"),
        **_project_permission_ctx(request.user, project),
    })


@login_required
def edit_member(request, pk, member_pk):
    """Change the role of an existing project member."""
    project = get_object_or_404(Project, pk=pk)
    member = get_object_or_404(ProjectMember, pk=member_pk, project=project)
    if not _require_manage_members(request, project):
        return redirect("projects:members", pk=pk)

    if request.method == "POST":
        form = ProjectMemberForm(request.POST, instance=member, project=project)
        if form.is_valid():
            form.save()  # save() re-syncs guardian permissions
            messages.success(request, _("Role updated for %(user)s.") % {"user": member.user})
            return redirect("projects:members", pk=pk)
    else:
        form = ProjectMemberForm(instance=member, project=project)

    return render(request, "projects/member_form.html", {
        "form": form,
        "project": project,
        "member": member,
        "title": _("Edit Member"),
        **_project_permission_ctx(request.user, project),
    })


@login_required
def remove_member(request, pk, member_pk):
    """Remove a user from a project (POST only)."""
    project = get_object_or_404(Project, pk=pk)
    member = get_object_or_404(ProjectMember, pk=member_pk, project=project)
    if not _require_manage_members(request, project):
        return redirect("projects:members", pk=pk)

    if request.method == "POST":
        username = str(member.user)
        member.delete()  # delete() revokes guardian permissions
        messages.success(request, _("%(user)s removed from project.") % {"user": username})

    return redirect("projects:members", pk=pk)
