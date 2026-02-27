from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm as _BasePasswordChangeForm
from django.utils.translation import gettext_lazy as _


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
