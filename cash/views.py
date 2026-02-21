from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.contrib import messages
from django.utils.translation import gettext_lazy as _

from projects.models import Project
from .models import Cashbox
from .forms import CashboxForm
from .services import create_cashbox


class CashboxListView(LoginRequiredMixin, ListView):
    template_name = "cash/cashbox_list.html"
    context_object_name = "cashboxes"

    def get_queryset(self):
        self.project = get_object_or_404(Project, pk=self.kwargs["project_pk"])
        return Cashbox.objects.filter(project=self.project, is_active=True).select_related("account", "currency")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["project"] = self.project
        ctx["title"] = _("Cashboxes")
        ctx["cashbox_data"] = [(cb, cb.balance()) for cb in ctx["cashboxes"]]
        return ctx


@login_required
def add_cashbox(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if not request.user.can_edit:
        messages.error(request, _("You do not have permission."))
        return redirect("projects:dashboard", pk=project_pk)

    if request.method == "POST":
        form = CashboxForm(request.POST)
        if form.is_valid():
            create_cashbox(
                project=project,
                name=form.cleaned_data["name"],
                currency=form.cleaned_data["currency"],
            )
            messages.success(request, _("Cashbox created."))
            return redirect(reverse("projects:dashboard", kwargs={"pk": project_pk}))
    else:
        form = CashboxForm()

    return render(request, "cash/cashbox_form.html", {
        "project": project,
        "form": form,
        "title": _("New Cashbox"),
    })
