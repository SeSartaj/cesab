from django import forms
from django.utils.translation import gettext_lazy as _
from .models import Contact


class ContactForm(forms.Form):
    name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        label=_("Name"),
    )
    phone = forms.CharField(
        max_length=50, required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        label=_("Phone"),
    )
    contact_type = forms.ChoiceField(
        choices=Contact.TYPE_CHOICES,
        initial=Contact.VENDOR,
        widget=forms.Select(attrs={"class": "form-select"}),
        label=_("Type"),
    )


# Backward-compat alias
VendorForm = ContactForm
