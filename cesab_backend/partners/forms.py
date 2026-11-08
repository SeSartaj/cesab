from django import forms
from django.utils.translation import gettext_lazy as _
from auth_users.models import User
from .models import ProjectPartner


class AddPartnerToProjectForm(forms.Form):
    name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        label=_("Name"),
    )
    user = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        label=_("System User (optional)"),
    )
    ownership_percent = forms.DecimalField(
        max_digits=5, decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0", "max": "100"}),
        label=_("Ownership %"),
    )
    capital_commitment = forms.DecimalField(
        max_digits=18, decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
        label=_("Capital Commitment"),
    )
    joined_at = forms.DateField(
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        label=_("Joined At"),
    )
