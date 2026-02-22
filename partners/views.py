from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, CreateView, UpdateView
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from projects.models import Project
from .models import Partner, ProjectPartner
from .forms import PartnerForm, AddPartnerToProjectForm, AddNewPartnerToProjectForm
from .services import add_partner_to_project, create_and_add_partner


class ShareholderListView(LoginRequiredMixin, ListView):
    template_name = "partners/shareholder_list.html"
    context_object_name = "project_partners"

    def get_queryset(self):
        self.project = get_object_or_404(Project, pk=self.kwargs["project_pk"])
        return ProjectPartner.objects.filter(project=self.project, is_active=True).select_related("partner")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["project"] = self.project
        ctx["title"] = _("Shareholders")
        return ctx


@login_required
def add_shareholder(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if not request.user.can_edit:
        messages.error(request, _("You do not have permission to perform this action."))
        return redirect("projects:dashboard", pk=project_pk)

    if request.method == "POST":
        form = AddPartnerToProjectForm(request.POST)
        if form.is_valid():
            add_partner_to_project(
                project=project,
                partner=form.cleaned_data["partner"],
                ownership_percent=form.cleaned_data["ownership_percent"],
                capital_commitment=form.cleaned_data["capital_commitment"],
                joined_at=form.cleaned_data["joined_at"],
            )
            messages.success(request, _("Partner added to project."))
            return redirect(reverse("projects:dashboard", kwargs={"pk": project_pk}) + "#shareholders")
    else:
        form = AddPartnerToProjectForm()

    return render(request, "partners/add_shareholder.html", {
        "project": project,
        "form": form,
        "title": _("Add Shareholder"),
    })


@login_required
def add_new_partner_to_project(request, project_pk):
    """Create a new partner and add them to the project in one form."""
    project = get_object_or_404(Project, pk=project_pk)
    if not request.user.can_edit:
        messages.error(request, _("You do not have permission to perform this action."))
        return redirect("projects:dashboard", pk=project_pk)

    if request.method == "POST":
        form = AddNewPartnerToProjectForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data
            _partner, pp = create_and_add_partner(
                project=project,
                name=d["name"],
                email=d.get("email", ""),
                phone=d.get("phone", ""),
                ownership_percent=d["ownership_percent"],
                capital_commitment=d["capital_commitment"],
                joined_at=d["joined_at"],
            )
            messages.success(request, _("Partner %(name)s added to project.") % {"name": d["name"]})
            return redirect(reverse("projects:dashboard", kwargs={"pk": project_pk}) + "#shareholders")
    else:
        form = AddNewPartnerToProjectForm(initial={"joined_at": timezone.now().date()})

    return render(request, "partners/add_new_partner.html", {
        "project": project,
        "form": form,
        "title": _("Add New Partner to Project"),
    })


class PartnerListView(LoginRequiredMixin, ListView):
    model = Partner
    template_name = "partners/partner_list.html"
    context_object_name = "partners"

    def get_queryset(self):
        return Partner.objects.filter(is_active=True)


class PartnerCreateView(LoginRequiredMixin, CreateView):
    model = Partner
    form_class = PartnerForm
    template_name = "partners/partner_form.html"

    def get_success_url(self):
        return reverse("partners:list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = _("New Partner")
        return ctx
