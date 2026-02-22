from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, CreateView, UpdateView
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from decimal import Decimal

from .models import Project
from .services import create_project
from .forms import ProjectForm
from partners.models import ProjectPartner
from cash.models import Cashbox
from journal.models import JournalEntry
from coa.models import Account


class ProjectListView(LoginRequiredMixin, ListView):
    model = Project
    template_name = "projects/project_list.html"
    context_object_name = "projects"

    def get_queryset(self):
        return Project.objects.filter(is_active=True)


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

    # Partner summary - return as tuples (pp, contributed, remaining, percent_done)
    partners = project.project_partners.filter(is_active=True).select_related(
        "partner", "capital_account", "current_account"
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
    })
