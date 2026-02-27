from django import forms
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from .models import Project, ProjectMember
from core.models import Currency

User = get_user_model()


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


class ProjectMemberForm(forms.ModelForm):
    """Add or edit a project member.

    Pass ``project=<Project instance>`` as a keyword argument so the user
    queryset excludes people already in the project (when adding) and
    excludes superusers (they always have full access anyway).
    """

    class Meta:
        model = ProjectMember
        fields = ["user", "role"]
        widgets = {
            "user": forms.Select(attrs={"class": "form-select"}),
            "role": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.project = project
        is_edit = bool(kwargs.get("instance"))

        if is_edit:
            # When editing we only allow changing the role; user is fixed.
            self.fields["user"].disabled = True
            self.fields["user"].queryset = User.objects.filter(is_active=True)
        else:
            # When adding, exclude superusers and users already in the project.
            existing_ids = (
                project.members.values_list("user_id", flat=True) if project else []
            )
            self.fields["user"].queryset = (
                User.objects.filter(is_active=True)
                .exclude(is_superuser=True)
                .exclude(pk__in=existing_ids)
            )

