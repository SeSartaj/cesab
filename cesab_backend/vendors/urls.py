from django.urls import path
from . import views

urlpatterns = [
    path("", views.ContactListView.as_view(), name="contacts"),
    path("add/", views.add_contact, name="add_contact"),
    path("<int:pk>/", views.ContactDetailView.as_view(), name="contact_detail"),
    # Backward-compat aliases so old URL names still resolve
    path("vendors/", views.ContactListView.as_view(), name="vendors"),
    path("vendors/add/", views.add_contact, name="add_vendor"),
    path("vendors/<int:pk>/", views.ContactDetailView.as_view(), name="vendor_detail"),
]
