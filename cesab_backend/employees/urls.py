from django.urls import path
from . import views

urlpatterns = [
    path("", views.EmployeeListView.as_view(), name="employees"),
    path("add/", views.add_employee, name="add_employee"),
]
