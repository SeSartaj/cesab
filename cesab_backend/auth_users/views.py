from django.contrib.auth.views import LoginView, LogoutView, PasswordChangeView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, FormView
from django.shortcuts import get_object_or_404, redirect

from .models import User
from .forms import (
    LoginForm,
    CesabPasswordChangeForm,
    UserCreateForm,
    UserEditForm,
    AdminPasswordChangeForm,
)


# ── Mixins ───────────────────────────────────────────────────────────────────

class SuperAdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restrict view to superusers only."""

    def test_func(self):
        return self.request.user.is_superuser

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            messages.error(self.request, _("You do not have permission to access user management."))
            return redirect("projects:list")
        return super().handle_no_permission()


# ── Existing auth views ───────────────────────────────────────────────────────

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


# ── Super-admin: User Management ─────────────────────────────────────────────

class UserListView(SuperAdminRequiredMixin, ListView):
    model = User
    template_name = "auth_users/user_list.html"
    context_object_name = "users"
    paginate_by = 25

    def get_queryset(self):
        qs = User.objects.prefetch_related("groups").order_by("username")
        q = self.request.GET.get("q", "").strip()
        if q:
            from django.db.models import Q
            qs = qs.filter(
                Q(username__icontains=q)
                | Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(email__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = _("User Management")
        ctx["q"] = self.request.GET.get("q", "")
        return ctx


class UserCreateView(SuperAdminRequiredMixin, CreateView):
    model = User
    form_class = UserCreateForm
    template_name = "auth_users/user_form.html"
    success_url = reverse_lazy("auth_users:user_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = _("Create User")
        ctx["action"] = _("Create")
        ctx["is_create"] = True
        return ctx

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            _("User %(u)s created successfully.") % {"u": self.object.username},
        )
        return response


class UserEditView(SuperAdminRequiredMixin, UpdateView):
    model = User
    form_class = UserEditForm
    template_name = "auth_users/user_form.html"
    success_url = reverse_lazy("auth_users:user_list")

    def get_object(self, queryset=None):
        return get_object_or_404(User, pk=self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = _("Edit User")
        ctx["action"] = _("Save Changes")
        ctx["is_create"] = False
        ctx["edited_user"] = self.object
        return ctx

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            _("User %(u)s updated successfully.") % {"u": self.object.username},
        )
        return response


class UserAdminPasswordChangeView(SuperAdminRequiredMixin, FormView):
    form_class = AdminPasswordChangeForm
    template_name = "auth_users/user_password_change.html"

    def get_target_user(self):
        return get_object_or_404(User, pk=self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["edited_user"] = self.get_target_user()
        ctx["title"] = _("Set Password")
        return ctx

    def form_valid(self, form):
        target = self.get_target_user()
        form.save(target)
        messages.success(
            self.request,
            _("Password for %(u)s has been changed.") % {"u": target.username},
        )
        return redirect("auth_users:user_list")


class UserDeleteView(SuperAdminRequiredMixin, DeleteView):
    model = User
    template_name = "auth_users/user_confirm_delete.html"
    success_url = reverse_lazy("auth_users:user_list")

    def get_object(self, queryset=None):
        obj = get_object_or_404(User, pk=self.kwargs["pk"])
        # Prevent deleting your own account
        if obj == self.request.user:
            messages.error(self.request, _("You cannot delete your own account."))
            return None
        return obj

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object is None:
            return redirect("auth_users:user_list")
        username = self.object.username
        self.object.delete()
        messages.success(request, _("User %(u)s has been deleted.") % {"u": username})
        return redirect(self.success_url)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["title"] = _("Delete User")
        return ctx


class UserToggleActiveView(SuperAdminRequiredMixin, UpdateView):
    """Toggle a user's is_active status via POST."""

    model = User
    fields = []  # no form needed
    http_method_names = ["post"]

    def get_object(self, queryset=None):
        obj = get_object_or_404(User, pk=self.kwargs["pk"])
        if obj == self.request.user:
            messages.error(self.request, _("You cannot deactivate your own account."))
            return None
        return obj

    def post(self, request, *args, **kwargs):
        user = self.get_object()
        if user is None:
            return redirect("auth_users:user_list")
        user.is_active = not user.is_active
        user.save(update_fields=["is_active"])
        state = _("activated") if user.is_active else _("deactivated")
        messages.success(
            request,
            _("User %(u)s has been %(state)s.") % {"u": user.username, "state": state},
        )
        return redirect("auth_users:user_list")
