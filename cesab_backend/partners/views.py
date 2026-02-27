from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from projects.models import Project
from projects.permissions import can_access_financial
from .models import ProjectPartner
from .forms import AddPartnerToProjectForm
from .services import add_partner_to_project


class ShareholderListView(LoginRequiredMixin, ListView):
    template_name = "partners/shareholder_list.html"
    context_object_name = "project_partners"

    def get_queryset(self):
        self.project = get_object_or_404(Project, pk=self.kwargs["project_pk"])
        return ProjectPartner.objects.filter(project=self.project, is_active=True).select_related("user", "project")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["project"] = self.project
        ctx["title"] = _("Shareholders")
        ctx["can_add_financial"] = can_access_financial(self.request.user, self.project)
        return ctx


@login_required
def add_shareholder(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if not can_access_financial(request.user, project):
        messages.error(request, _("You do not have permission to perform this action."))
        return redirect("projects:dashboard", pk=project_pk)

    if request.method == "POST":
        form = AddPartnerToProjectForm(request.POST)
        if form.is_valid():
            add_partner_to_project(
                project=project,
                name=form.cleaned_data["name"],
                user=form.cleaned_data.get("user"),
                ownership_percent=form.cleaned_data["ownership_percent"],
                capital_commitment=form.cleaned_data["capital_commitment"],
                joined_at=form.cleaned_data["joined_at"],
            )
            messages.success(request, _("Partner added to project."))
            return redirect(reverse("projects:dashboard", kwargs={"pk": project_pk}) + "#shareholders")
    else:
        form = AddPartnerToProjectForm(initial={"joined_at": timezone.now().date()})

    return render(request, "partners/add_shareholder.html", {
        "project": project,
        "form": form,
        "title": _("Add Shareholder"),
    })
