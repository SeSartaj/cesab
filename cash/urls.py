from django.urls import path
from . import views

urlpatterns = [
    path("", views.CashboxListView.as_view(), name="cashboxes"),
    path("add/", views.add_cashbox, name="add_cashbox"),
]
