from django import forms
from django.utils.translation import gettext_lazy as _
from .models import Project
from core.models import Currency


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ["name", "base_currency", "description", "start_date"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "base_currency": forms.Select(attrs={"class": "form-select"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "start_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["base_currency"].queryset = Currency.objects.filter(is_active=True)
        self.fields["description"].required = False
        self.fields["start_date"].required = False
