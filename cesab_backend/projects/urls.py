from django.urls import path, include
from . import views

app_name = "projects"

urlpatterns = [
    path("", views.ProjectListView.as_view(), name="list"),
    path("new/", views.ProjectCreateView.as_view(), name="create"),
    path("<int:pk>/", views.project_dashboard, name="dashboard"),
    path("<int:pk>/edit/", views.ProjectUpdateView.as_view(), name="edit"),
    # Member management
    path("<int:pk>/members/", views.project_members, name="members"),
    path("<int:pk>/members/add/", views.add_member, name="add_member"),
    path("<int:pk>/members/<int:member_pk>/edit/", views.edit_member, name="edit_member"),
    path("<int:pk>/members/<int:member_pk>/remove/", views.remove_member, name="remove_member"),
    # Sub-resources
    path("<int:project_pk>/shareholders/", include("partners.urls")),
    path("<int:project_pk>/cashboxes/", include("cash.urls")),
    path("<int:project_pk>/vendors/", include("vendors.urls")),
    path("<int:project_pk>/employees/", include("employees.urls")),
    path("<int:project_pk>/journal/", include("journal.urls")),
    path("<int:project_pk>/transactions/", include("transactions.urls")),
    path("<int:project_pk>/coa/", include("coa.urls")),
    path("<int:project_pk>/inventory/", include("inventory.urls")),
]
