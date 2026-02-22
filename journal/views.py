from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, DetailView
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.contrib import messages
from django.utils.translation import gettext_lazy as _

from projects.models import Project
from .models import JournalEntry, TRANSACTION_TYPES
import transactions.services as tx_svc


class JournalEntryListView(LoginRequiredMixin, ListView):
    template_name = "journal/je_list.html"
    context_object_name = "entries"
    paginate_by = 30

    def get_queryset(self):
        self.project = get_object_or_404(Project, pk=self.kwargs["project_pk"])
        qs = JournalEntry.objects.filter(project=self.project).prefetch_related("lines")
        tx_type = self.request.GET.get("tx_type")
        date_from = self.request.GET.get("date_from")
        date_to = self.request.GET.get("date_to")
        if tx_type:
            qs = qs.filter(transaction_type=tx_type)
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["project"] = self.project
        ctx["title"] = _("Journal Entries")
        ctx["tx_types"] = TRANSACTION_TYPES
        return ctx


class JournalEntryDetailView(LoginRequiredMixin, DetailView):
    model = JournalEntry
    template_name = "journal/je_detail.html"
    context_object_name = "entry"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["project"] = self.object.project
        ctx["corrections"] = self.object.corrections.all()
        return ctx


@login_required
def create_correction(request, project_pk, je_pk):
    """Create a counter-balancing correction entry. Journal entries can never be deleted."""
    project = get_object_or_404(Project, pk=project_pk)
    original_je = get_object_or_404(JournalEntry, pk=je_pk, project=project)

    if not request.user.can_edit:
        messages.error(request, _("You do not have permission to perform this action."))
        return redirect(reverse("projects:je_detail", kwargs={"project_pk": project_pk, "pk": je_pk}))

    if request.method == "POST":
        description = request.POST.get("description", "").strip()
        correction_je = tx_svc.create_correction_entry(
            original_je=original_je,
            user=request.user,
            description=description,
        )
        messages.success(
            request,
            _("Correction entry JE-%(pk)04d created successfully.") % {"pk": correction_je.pk}
        )
        return redirect(reverse("projects:je_detail", kwargs={"project_pk": project_pk, "pk": correction_je.pk}))

    return render(request, "journal/create_correction.html", {
        "project": project,
        "original_je": original_je,
        "title": _("Create Correction Entry"),
    })
