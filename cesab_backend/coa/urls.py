from django.urls import path
from . import views

urlpatterns = [
    path("", views.AccountListView.as_view(), name="coa"),
    path("add/", views.account_create, name="account_create"),
    path("<int:pk>/edit/", views.account_edit, name="account_edit"),
    path("trial-balance/", views.trial_balance, name="trial_balance"),
]
