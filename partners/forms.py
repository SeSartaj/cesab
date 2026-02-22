from django import forms
from django.utils.translation import gettext_lazy as _
from .models import Partner, ProjectPartner


class PartnerForm(forms.ModelForm):
    class Meta:
        model = Partner
        fields = ["name", "email", "phone"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].required = False
        self.fields["phone"].required = False


class AddPartnerToProjectForm(forms.Form):
    partner = forms.ModelChoiceField(
        queryset=Partner.objects.filter(is_active=True),
        widget=forms.Select(attrs={"class": "form-select"}),
        label=_("Partner"),
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


class AddNewPartnerToProjectForm(forms.Form):
    """Combined form to create a new Partner and add them to a project in one go."""
    # Partner fields
    name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        label=_("Partner Name"),
    )
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={"class": "form-control"}),
        label=_("Email"),
    )
    phone = forms.CharField(
        max_length=50, required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        label=_("Phone"),
    )
    # Project partner fields
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
