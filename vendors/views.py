from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, DetailView
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.contrib import messages
from django.utils.translation import gettext_lazy as _

from projects.models import Project
from .models import Vendor
from .forms import VendorForm
from .services import create_vendor


class VendorListView(LoginRequiredMixin, ListView):
    template_name = "vendors/vendor_list.html"
    context_object_name = "vendors"

    def get_queryset(self):
        self.project = get_object_or_404(Project, pk=self.kwargs["project_pk"])
        return Vendor.objects.filter(project=self.project, is_active=True)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["project"] = self.project
        ctx["title"] = _("Vendors")
        return ctx


@login_required
def add_vendor(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if not request.user.can_edit:
        messages.error(request, _("You do not have permission."))
        return redirect("projects:dashboard", pk=project_pk)

    if request.method == "POST":
        form = VendorForm(request.POST)
        if form.is_valid():
            create_vendor(
                project=project,
                name=form.cleaned_data["name"],
                phone=form.cleaned_data.get("phone", ""),
            )
            messages.success(request, _("Vendor created."))
            return redirect(reverse("projects:dashboard", kwargs={"pk": project_pk}))
    else:
        form = VendorForm()

    return render(request, "vendors/vendor_form.html", {
        "project": project,
        "form": form,
        "title": _("New Vendor"),
    })


class VendorDetailView(LoginRequiredMixin, DetailView):
    model = Vendor
    template_name = "vendors/vendor_detail.html"
    context_object_name = "vendor"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["project"] = self.object.project
        return ctx
