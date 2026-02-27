from django.contrib.auth.views import LoginView, LogoutView
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from .forms import LoginForm


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
