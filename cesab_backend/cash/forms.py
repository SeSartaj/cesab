from django import forms
from django.utils.translation import gettext_lazy as _
from .models import Cashbox
from core.models import Currency


class CashboxForm(forms.Form):
    name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        label=_("Cashbox Name"),
    )
    currency = forms.ModelChoiceField(
        queryset=Currency.objects.filter(is_active=True),
        widget=forms.Select(attrs={"class": "form-select"}),
        label=_("Currency"),
    )
