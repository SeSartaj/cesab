from django.urls import path
from . import views

urlpatterns = [
    path("", views.VendorListView.as_view(), name="vendors"),
    path("add/", views.add_vendor, name="add_vendor"),
    path("<int:pk>/", views.VendorDetailView.as_view(), name="vendor_detail"),
]
