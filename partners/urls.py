from django.urls import path
from . import views

urlpatterns = [
    path("", views.ShareholderListView.as_view(), name="shareholders"),
    path("add/", views.add_shareholder, name="add_shareholder"),
    path("add-new/", views.add_new_partner_to_project, name="add_new_partner_to_project"),
]
