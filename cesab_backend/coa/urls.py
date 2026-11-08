from django.urls import path
from . import views

urlpatterns = [
    path("", views.AccountListView.as_view(), name="coa"),
]
