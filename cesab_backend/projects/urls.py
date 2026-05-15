from django.urls import path, include
from . import views
from . import report_views

app_name = "projects"

urlpatterns = [
    path("", views.ProjectListView.as_view(), name="list"),
    path("new/", views.ProjectCreateView.as_view(), name="create"),
    path("<int:pk>/", views.project_dashboard, name="dashboard"),
    path("<int:pk>/edit/", views.ProjectUpdateView.as_view(), name="edit"),
    path("<int:pk>/reports/", views.financial_reports_summary, name="financial_reports"),
    # Financial reports — detail pages
    path("<int:pk>/reports/profit-and-loss/", report_views.profit_and_loss, name="report_profit_loss"),
    path("<int:pk>/reports/balance-sheet/", report_views.balance_sheet, name="report_balance_sheet"),
    path("<int:pk>/reports/purchases/", report_views.purchase_report, name="report_purchases"),
    path("<int:pk>/reports/tax/", report_views.tax_report, name="report_tax"),
    # Member management
    path("<int:pk>/members/", views.project_members, name="members"),
    path("<int:pk>/members/add/", views.add_member, name="add_member"),
    path("<int:pk>/members/<int:member_pk>/edit/", views.edit_member, name="edit_member"),
    path("<int:pk>/members/<int:member_pk>/remove/", views.remove_member, name="remove_member"),
    # Sub-resources
    path("<int:project_pk>/shareholders/", include("partners.urls")),
    path("<int:project_pk>/cashboxes/", include("cash.urls")),
    path("<int:project_pk>/contacts/", include("vendors.urls")),
    path("<int:project_pk>/employees/", include("employees.urls")),
    path("<int:project_pk>/journal/", include("journal.urls")),
    path("<int:project_pk>/transactions/", include("transactions.urls")),
    path("<int:project_pk>/coa/", include("coa.urls")),
    path("<int:project_pk>/inventory/", include("inventory.urls")),
    path("<int:project_pk>/documents/", include("documents.urls")),
]
