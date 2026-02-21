from django.urls import path, include
from . import views

app_name = "projects"

urlpatterns = [
    path("", views.ProjectListView.as_view(), name="list"),
    path("new/", views.ProjectCreateView.as_view(), name="create"),
    path("<int:pk>/", views.project_dashboard, name="dashboard"),
    path("<int:pk>/edit/", views.ProjectUpdateView.as_view(), name="edit"),
    # Sub-resources
    path("<int:project_pk>/shareholders/", include("partners.urls")),
    path("<int:project_pk>/cashboxes/", include("cash.urls")),
    path("<int:project_pk>/vendors/", include("vendors.urls")),
    path("<int:project_pk>/employees/", include("employees.urls")),
    path("<int:project_pk>/journal/", include("journal.urls")),
    path("<int:project_pk>/transactions/", include("transactions.urls")),
    path("<int:project_pk>/coa/", include("coa.urls")),
]
