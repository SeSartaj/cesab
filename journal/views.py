from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _

from projects.models import Project
from .models import JournalEntry, TRANSACTION_TYPES


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
        return ctx
