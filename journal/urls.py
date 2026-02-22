from django.urls import path
from . import views

urlpatterns = [
    path("", views.JournalEntryListView.as_view(), name="journal"),
    path("<int:pk>/", views.JournalEntryDetailView.as_view(), name="je_detail"),
    path("<int:je_pk>/correct/", views.create_correction, name="create_correction"),
]
