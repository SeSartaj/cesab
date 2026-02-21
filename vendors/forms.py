from django import forms
from django.utils.translation import gettext_lazy as _


class VendorForm(forms.Form):
    name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        label=_("Vendor Name"),
    )
    phone = forms.CharField(
        max_length=50, required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        label=_("Phone"),
    )
