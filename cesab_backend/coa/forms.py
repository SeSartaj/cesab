from django import forms
from django.utils.translation import gettext_lazy as _
from .models import Account


class AccountForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = ["code", "name", "account_type", "parent", "is_tax_account", "is_active"]
        widgets = {
            "code": forms.TextInput(attrs={"class": "form-control"}),
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "account_type": forms.Select(attrs={"class": "form-select"}),
            "parent": forms.Select(attrs={"class": "form-select"}),
            "is_tax_account": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, project, *args, account_type=None, **kwargs):
        super().__init__(*args, **kwargs)
        parent_qs = Account.objects.filter(project=project, is_active=True)
        if account_type:
            parent_qs = parent_qs.filter(account_type=account_type)
        self.fields["parent"].queryset = parent_qs
        self.fields["parent"].required = False
