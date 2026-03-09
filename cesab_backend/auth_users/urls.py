from django.urls import path
from . import views

app_name = "auth_users"

urlpatterns = [
    path("login/", views.CesabLoginView.as_view(), name="login"),
    path("logout/", views.CesabLogoutView.as_view(), name="logout"),
    path("password/change/", views.CesabPasswordChangeView.as_view(), name="password_change"),

    # Super-admin user management
    path("users/", views.UserListView.as_view(), name="user_list"),
    path("users/create/", views.UserCreateView.as_view(), name="user_create"),
    path("users/<int:pk>/edit/", views.UserEditView.as_view(), name="user_edit"),
    path("users/<int:pk>/password/", views.UserAdminPasswordChangeView.as_view(), name="user_password"),
    path("users/<int:pk>/delete/", views.UserDeleteView.as_view(), name="user_delete"),
    path("users/<int:pk>/toggle-active/", views.UserToggleActiveView.as_view(), name="user_toggle_active"),
]
