from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm as _BasePasswordChangeForm,
    UserCreationForm,
    UserChangeForm,
)
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .models import User


# ── helpers ─────────────────────────────────────────────────────────────────

def _styled(widget, extra=None):
    attrs = {"class": "form-control"}
    if extra:
        attrs.update(extra)
    widget.attrs.update(attrs)
    return widget


# ── existing forms ───────────────────────────────────────────────────────────

class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label=_("Username"),
        widget=forms.TextInput(attrs={"class": "form-control", "autofocus": True, "placeholder": _("Username")}),
    )
    password = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": _("Password")}),
    )


class CesabPasswordChangeForm(_BasePasswordChangeForm):
    """Styled wrapper around Django's built-in PasswordChangeForm."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


# ── super-admin user management forms ────────────────────────────────────────

class UserCreateForm(forms.ModelForm):
    """Form for super-admins to create new users."""

    password1 = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
        help_text=_("At least 8 characters."),
    )
    password2 = forms.CharField(
        label=_("Confirm Password"),
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
    )
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        required=False,
        label=_("Groups"),
        widget=forms.CheckboxSelectMultiple,
        help_text=_("Assign the user to one or more groups."),
    )

    class Meta:
        model = User
        fields = [
            "username", "first_name", "last_name", "email",
            "is_active", "is_staff", "is_superuser", "groups",
        ]
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control"}),
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
        }
        help_texts = {
            "username": _("Required. Letters, digits and @/./+/-/_ only."),
            "is_staff": _("Grants access to the Django admin site."),
            "is_superuser": _("Full unrestricted access to everything."),
        }

    def clean_password2(self):
        p1 = self.cleaned_data.get("password1", "")
        p2 = self.cleaned_data.get("password2", "")
        if p1 and p2 and p1 != p2:
            raise ValidationError(_("The two password fields didn't match."))
        if p1 and len(p1) < 8:
            raise ValidationError(_("Password must be at least 8 characters."))
        return p2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
            self.save_m2m()
        return user


class UserEditForm(forms.ModelForm):
    """Form for super-admins to edit an existing user's profile & permissions."""

    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        required=False,
        label=_("Groups"),
        widget=forms.CheckboxSelectMultiple,
        help_text=_("Assign the user to one or more groups."),
    )

    class Meta:
        model = User
        fields = [
            "username", "first_name", "last_name", "email",
            "is_active", "is_staff", "is_superuser", "groups",
        ]
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control"}),
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
        }
        help_texts = {
            "is_staff": _("Grants access to the Django admin site."),
            "is_superuser": _("Full unrestricted access to everything."),
        }


class AdminPasswordChangeForm(forms.Form):
    """Lets a super-admin set a user's password without knowing the old one."""

    password1 = forms.CharField(
        label=_("New Password"),
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
        help_text=_("At least 8 characters."),
    )
    password2 = forms.CharField(
        label=_("Confirm New Password"),
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
    )

    def clean_password2(self):
        p1 = self.cleaned_data.get("password1", "")
        p2 = self.cleaned_data.get("password2", "")
        if p1 and p2 and p1 != p2:
            raise ValidationError(_("The two password fields didn't match."))
        if p1 and len(p1) < 8:
            raise ValidationError(_("Password must be at least 8 characters."))
        return p2

    def save(self, user):
        user.set_password(self.cleaned_data["password1"])
        user.save()
        return user
