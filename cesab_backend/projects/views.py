from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, CreateView, UpdateView
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.db.models import Q
from decimal import Decimal

from .models import Project, ProjectMember
from .services import create_project, add_member, remove_member
from .permissions import get_role, require_admin
from .forms import ProjectForm, InviteMemberForm
from partners.models import ProjectPartner
from cash.models import Cashbox
from journal.models import JournalEntry
from coa.models import Account


# ─── Queryset helper ────────────────────────────────────────────────────────

def _accessible_projects(user):
    """Return projects visible to this user (any role or partner)."""
    if user.is_superuser:
        return Project.objects.filter(is_active=True)
    qs = Project.objects.filter(is_active=True)
    member_pks = ProjectMember.objects.filter(user=user).values_list("project_id", flat=True)
    partner_pks = ProjectPartner.objects.filter(
        user=user, is_active=True
    ).values_list("project_id", flat=True)
    return qs.filter(Q(pk__in=member_pks) | Q(pk__in=partner_pks)).distinct()


class ProjectListView(LoginRequiredMixin, ListView):
    model = Project
    template_name = "projects/project_list.html"
    context_object_name = "projects"

    def get_queryset(self):
        return _accessible_projects(self.request.user)


class ProjectCreateView(LoginRequiredMixin, CreateView):
    form_class = ProjectForm
    template_name = "projects/project_form.html"

    def form_valid(self, form):
        data = form.cleaned_data
        project = create_project(
            name=data["name"],
            base_currency=data["base_currency"],
            description=data.get("description", ""),
            start_date=data.get("start_date"),
            created_by=self.request.user,
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

    def get_success_url(self):
        return reverse("projects:dashboard", kwargs={"pk": self.object.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = _("Edit Project")
        ctx["project"] = self.object
        return ctx


@login_required
def project_dashboard(request, pk):
    project = get_object_or_404(Project, pk=pk)

    # Access check: superuser, project member, or partner user
    if not request.user.is_superuser:
        is_member = ProjectMember.objects.filter(project=project, user=request.user).exists()
        is_partner = ProjectPartner.objects.filter(
            project=project, user=request.user, is_active=True
        ).exists()
        if not (is_member or is_partner):
            messages.error(request, _("You do not have access to this project."))
            return redirect("projects:list")

    user_role = get_role(request.user, project)

    # Partner summary - return as tuples (pp, contributed, remaining, percent_done)
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

    # Total payables (liability accounts with credit balance)
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
        "user_role": user_role,
        "is_project_admin": user_role == "admin",
        "can_do_accounting": user_role in ("admin", "accountant"),
    })


# ─── Member Management ──────────────────────────────────────────────────────

@login_required
def manage_members(request, pk):
    """List project members and allow the project admin to invite/remove members."""
    project = get_object_or_404(Project, pk=pk)

    denied = require_admin(request, project)
    if denied:
        return denied

    members = project.members.select_related("user").order_by("role", "user__username")
    form = InviteMemberForm()
    found_user = None

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "search":
            form = InviteMemberForm(request.POST)
            if form.is_valid():
                username = form.cleaned_data["username"].strip()
                from django.contrib.auth import get_user_model
                User = get_user_model()
                try:
                    found_user = User.objects.get(username=username)
                    if project.members.filter(user=found_user).exists():
                        messages.warning(
                            request,
                            _("%(username)s is already a member of this project.") % {"username": username},
                        )
                        found_user = None
                except User.DoesNotExist:
                    messages.error(
                        request,
                        _('No user found with username "%(username)s".') % {"username": username},
                    )

        elif action == "add":
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user_id = request.POST.get("user_id")
            role = request.POST.get("role", "viewer")
            try:
                target_user = User.objects.get(pk=user_id)
                pm, created = add_member(project, request.user, target_user, role)
                if created:
                    messages.success(
                        request,
                        _("%(username)s added to the project as %(role)s.")
                        % {"username": target_user.username, "role": role},
                    )
                else:
                    messages.warning(request, _("User is already a member."))
            except User.DoesNotExist:
                messages.error(request, _("User not found."))
            except Exception as exc:
                messages.error(request, str(exc))
            return redirect("projects:manage_members", pk=pk)

        elif action == "remove":
            member_id = request.POST.get("member_id")
            member = get_object_or_404(ProjectMember, pk=member_id, project=project)
            try:
                username = member.user.username
                remove_member(project, request.user, member)
                messages.success(
                    request,
                    _("%(username)s has been removed from the project.") % {"username": username},
                )
            except ValueError as exc:
                messages.error(request, str(exc))
            return redirect("projects:manage_members", pk=pk)

    return render(request, "projects/members.html", {
        "project": project,
        "members": members,
        "form": form,
        "found_user": found_user,
        "user_role": "admin",
    })
