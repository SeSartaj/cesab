from django.db import models
from django.utils.translation import gettext_lazy as _
from decimal import Decimal


class InventoryItem(models.Model):
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="inventory_items",
        verbose_name=_("Project"),
    )
    name = models.CharField(max_length=200, verbose_name=_("Item Name"))
    unit = models.CharField(
        max_length=50,
        verbose_name=_("Unit"),
        help_text=_("e.g. kg, bag, ton, liter, box"),
    )
    inventory_account = models.ForeignKey(
        "coa.Account",
        on_delete=models.PROTECT,
        related_name="inventory_accounts",
        verbose_name=_("Inventory Account"),
    )
    expense_account = models.ForeignKey(
        "coa.Account",
        on_delete=models.PROTECT,
        related_name="inventory_expense_accounts",
        verbose_name=_("Expense Account"),
    )
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Inventory Item")
        verbose_name_plural = _("Inventory Items")
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.unit})"

    def quantity_on_hand(self):
        """Calculate current quantity from movements."""
        from decimal import Decimal
        qty = Decimal("0")
        for mv in self.movements.all():
            if mv.movement_type in ("purchase", "adjustment", "contribution"):
                qty += mv.quantity
            elif mv.movement_type == "consumption":
                qty -= mv.quantity
        return qty

    def weighted_average_cost(self):
        """Weighted average unit cost from all inbound movements."""
        from decimal import Decimal
        total_qty = Decimal("0")
        total_cost = Decimal("0")
        for mv in self.movements.filter(movement_type__in=("purchase", "adjustment", "contribution")):
            if mv.quantity > 0:
                total_qty += mv.quantity
                total_cost += mv.total_cost
        if total_qty == 0:
            return Decimal("0")
        return (total_cost / total_qty).quantize(Decimal("0.000001"))


class InventoryMovement(models.Model):
    MOVEMENT_TYPES = [
        ("purchase", _("Purchase")),
        ("consumption", _("Consumption")),
        ("adjustment", _("Adjustment")),
        ("contribution", _("Partner Contribution")),
    ]

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="inventory_movements",
        verbose_name=_("Project"),
    )
    item = models.ForeignKey(
        "inventory.InventoryItem",
        on_delete=models.PROTECT,
        related_name="movements",
        verbose_name=_("Item"),
    )
    movement_type = models.CharField(
        max_length=20,
        choices=MOVEMENT_TYPES,
        verbose_name=_("Movement Type"),
    )
    quantity = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        verbose_name=_("Quantity"),
    )
    unit_cost = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        verbose_name=_("Unit Cost"),
    )
    total_cost = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        verbose_name=_("Total Cost"),
    )
    project_partner = models.ForeignKey(
        "partners.ProjectPartner",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        verbose_name=_("Project Partner"),
        help_text=_("Required only for partner contribution"),
    )
    vendor = models.ForeignKey(
        "vendors.Vendor",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="inventory_movements",
        verbose_name=_("Vendor"),
        help_text=_("Vendor for cash-to-vendor purchases"),
    )
    journal_entry = models.ForeignKey(
        "journal.JournalEntry",
        on_delete=models.PROTECT,
        related_name="inventory_movements",
        verbose_name=_("Journal Entry"),
    )
    created_by = models.ForeignKey(
        "auth_users.User",
        on_delete=models.PROTECT,
        verbose_name=_("Created By"),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Inventory Movement")
        verbose_name_plural = _("Inventory Movements")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_movement_type_display()} — {self.item.name} x {self.quantity}"
