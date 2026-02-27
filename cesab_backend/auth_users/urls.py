from django.urls import path
from . import views

app_name = "auth_users"

urlpatterns = [
    path("login/", views.CesabLoginView.as_view(), name="login"),
    path("logout/", views.CesabLogoutView.as_view(), name="logout"),
    path("password/change/", views.CesabPasswordChangeView.as_view(), name="password_change"),
]
