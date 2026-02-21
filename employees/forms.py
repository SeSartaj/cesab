from django import forms
from django.utils.translation import gettext_lazy as _
from .models import ProjectEmployee


class EmployeeForm(forms.Form):
    SALARY_TYPES = [
        ("monthly", _("Monthly")),
        ("daily", _("Daily")),
    ]
    name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        label=_("Name"),
    )
    salary_type = forms.ChoiceField(
        choices=SALARY_TYPES,
        widget=forms.Select(attrs={"class": "form-select"}),
        label=_("Salary Type"),
    )
    salary_amount = forms.DecimalField(
        max_digits=18, decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
        label=_("Salary Amount"),
    )
