from django.contrib.auth.views import LoginView, LogoutView, PasswordChangeView
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.contrib import messages
from .forms import LoginForm, CesabPasswordChangeForm


class CesabLoginView(LoginView):
    form_class = LoginForm
    template_name = "auth_users/login.html"
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = _("Login")
        return ctx


class CesabLogoutView(LogoutView):
    next_page = reverse_lazy("auth_users:login")


class CesabPasswordChangeView(PasswordChangeView):
    form_class = CesabPasswordChangeForm
    template_name = "auth_users/password_change.html"
    success_url = reverse_lazy("projects:list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = _("Change Password")
        return ctx

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, _("Your password has been changed successfully."))
        return response
