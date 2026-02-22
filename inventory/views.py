from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from projects.models import Project
from .models import InventoryItem, InventoryMovement
from . import forms as inv_forms
from . import services as svc


def _require_perm(request, project_pk, perm="inventory.add_inventorymovement"):
    if not request.user.has_perm(perm) and not request.user.is_superuser:
        messages.error(request, _("You do not have permission to perform this action."))
        return redirect("projects:dashboard", pk=project_pk)
    return None


@login_required
def item_list(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    items = InventoryItem.objects.filter(project=project, is_active=True)
    return render(request, "inventory/item_list.html", {
        "project": project,
        "items": items,
        "title": _("Inventory"),
    })


@login_required
def add_item(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    denied = _require_perm(request, project_pk, "inventory.add_inventoryitem")
    if denied:
        return denied

    if request.method == "POST":
        form = inv_forms.InventoryItemForm(request.POST)
        if form.is_valid():
            svc.create_inventory_item(
                project=project,
                name=form.cleaned_data["name"],
                unit=form.cleaned_data["unit"],
            )
            messages.success(request, _("Inventory item created."))
            return redirect(reverse("projects:inventory", kwargs={"project_pk": project_pk}))
    else:
        form = inv_forms.InventoryItemForm()

    return render(request, "inventory/item_form.html", {
        "project": project,
        "form": form,
        "title": _("New Inventory Item"),
    })


@login_required
def inventory_purchase(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    denied = _require_perm(request, project_pk)
    if denied:
        return denied

    if request.method == "POST":
        form = inv_forms.InventoryPurchaseForm(project, request.POST)
        if form.is_valid():
            d = form.cleaned_data
            use_base = d.get("use_base_currency", True)
            currency = None if use_base else d.get("currency")
            exchange_rate = 1 if use_base else (d.get("exchange_rate") or 1)
            svc.record_inventory_purchase(
                project=project, user=request.user,
                date=d["date"], item=d["item"],
                quantity=d["quantity"], unit_cost=d["unit_cost"],
                cashbox=d["cashbox"],
                description=d.get("description", ""),
                currency=currency, exchange_rate=exchange_rate,
            )
            messages.success(request, _("Inventory purchase recorded."))
            return redirect(reverse("projects:inventory", kwargs={"project_pk": project_pk}))
    else:
        form = inv_forms.InventoryPurchaseForm(
            project, initial={"date": timezone.now().date(), "use_base_currency": True}
        )

    return render(request, "inventory/movement_form.html", {
        "project": project,
        "form": form,
        "title": _("Inventory Purchase"),
        "show_currency": True,
    })


@login_required
def inventory_consumption(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    denied = _require_perm(request, project_pk)
    if denied:
        return denied

    if request.method == "POST":
        form = inv_forms.InventoryConsumptionForm(project, request.POST)
        if form.is_valid():
            d = form.cleaned_data
            svc.record_inventory_consumption(
                project=project, user=request.user,
                date=d["date"], item=d["item"],
                quantity=d["quantity"],
                description=d.get("description", ""),
            )
            messages.success(request, _("Inventory consumption recorded."))
            return redirect(reverse("projects:inventory", kwargs={"project_pk": project_pk}))
    else:
        form = inv_forms.InventoryConsumptionForm(project, initial={"date": timezone.now().date()})

    return render(request, "inventory/movement_form.html", {
        "project": project,
        "form": form,
        "title": _("Inventory Consumption"),
        "show_currency": False,
    })


@login_required
def inventory_adjustment(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    denied = _require_perm(request, project_pk)
    if denied:
        return denied

    if request.method == "POST":
        form = inv_forms.InventoryAdjustmentForm(project, request.POST)
        if form.is_valid():
            d = form.cleaned_data
            svc.record_inventory_adjustment(
                project=project, user=request.user,
                date=d["date"], item=d["item"],
                quantity=d["quantity"], unit_cost=d["unit_cost"],
                is_increase=(d["direction"] == "increase"),
                description=d.get("description", ""),
            )
            messages.success(request, _("Inventory adjustment recorded."))
            return redirect(reverse("projects:inventory", kwargs={"project_pk": project_pk}))
    else:
        form = inv_forms.InventoryAdjustmentForm(
            project, initial={"date": timezone.now().date(), "direction": "increase"}
        )

    return render(request, "inventory/movement_form.html", {
        "project": project,
        "form": form,
        "title": _("Inventory Adjustment"),
        "show_currency": False,
    })


@login_required
def partner_inventory_contribution(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    denied = _require_perm(request, project_pk)
    if denied:
        return denied

    if request.method == "POST":
        form = inv_forms.PartnerInventoryContributionForm(project, request.POST)
        if form.is_valid():
            d = form.cleaned_data
            use_base = d.get("use_base_currency", True)
            currency = None if use_base else d.get("currency")
            exchange_rate = 1 if use_base else (d.get("exchange_rate") or 1)
            svc.record_partner_inventory_contribution(
                project=project, user=request.user,
                date=d["date"], item=d["item"],
                quantity=d["quantity"], unit_cost=d["unit_cost"],
                project_partner=d["project_partner"],
                description=d.get("description", ""),
                currency=currency, exchange_rate=exchange_rate,
            )
            messages.success(request, _("Partner inventory contribution recorded."))
            return redirect(reverse("projects:inventory", kwargs={"project_pk": project_pk}))
    else:
        form = inv_forms.PartnerInventoryContributionForm(
            project, initial={"date": timezone.now().date(), "use_base_currency": True}
        )

    return render(request, "inventory/movement_form.html", {
        "project": project,
        "form": form,
        "title": _("Partner Inventory Contribution"),
        "show_currency": True,
    })
