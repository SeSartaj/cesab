from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.contrib import messages
from django.utils.translation import gettext_lazy as _

from projects.models import Project
from projects.permissions import require_accounting
from .models import ProjectEmployee
from .forms import EmployeeForm
from .services import create_employee


class EmployeeListView(LoginRequiredMixin, ListView):
    template_name = "employees/employee_list.html"
    context_object_name = "employees"

    def get_queryset(self):
        self.project = get_object_or_404(Project, pk=self.kwargs["project_pk"])
        return ProjectEmployee.objects.filter(project=self.project, is_active=True)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["project"] = self.project
        ctx["title"] = _("Employees")
        return ctx


@login_required
def add_employee(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    denied = require_accounting(request, project)
    if denied:
        return denied

    if request.method == "POST":
        form = EmployeeForm(request.POST)
        if form.is_valid():
            create_employee(
                project=project,
                user=request.user,
                name=form.cleaned_data["name"],
                salary_type=form.cleaned_data["salary_type"],
                salary_amount=form.cleaned_data["salary_amount"],
            )
            messages.success(request, _("Employee added."))
            return redirect(reverse("projects:dashboard", kwargs={"pk": project_pk}))
    else:
        form = EmployeeForm()

    return render(request, "employees/employee_form.html", {
        "project": project,
        "form": form,
        "title": _("Add Employee"),
    })
