from django.urls import path
from . import views

urlpatterns = [
    path("", views.item_list, name="inventory"),
    path("add-item/", views.add_item, name="add_inventory_item"),
    path("purchase/", views.inventory_purchase, name="inventory_purchase"),
    path("consumption/", views.inventory_consumption, name="inventory_consumption"),
    path("adjustment/", views.inventory_adjustment, name="inventory_adjustment"),
    path("partner-contribution/", views.partner_inventory_contribution, name="partner_inventory_contribution"),
]
