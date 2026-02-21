
---

# Updated Apps Structure

```python
inventory/
    InventoryItem
    InventoryMovement

assets/
    Asset
```

---


this is our second iteration


# inventory app

## InventoryItem


```python
class InventoryItem(models.Model):

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="inventory_items"
    )

    name = models.CharField(max_length=200)

    unit = models.CharField(
        max_length=50,
        help_text="e.g. kg, bag, ton, liter, box"
    )

    inventory_account = models.ForeignKey(
        "coa.Account",
        on_delete=models.PROTECT,
        related_name="inventory_accounts"
    )

    expense_account = models.ForeignKey(
        "coa.Account",
        on_delete=models.PROTECT,
        related_name="inventory_expense_accounts"
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
```

---

## InventoryMovement

```python
class InventoryMovement(models.Model):

    MOVEMENT_TYPES = [
        ("purchase", "Purchase"),
        ("consumption", "Consumption"),
        ("adjustment", "Adjustment"),
        ("contribution", "Partner Contribution"),
    ]

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="inventory_movements"
    )

    item = models.ForeignKey(
        "inventory.InventoryItem",
        on_delete=models.PROTECT,
        related_name="movements"
    )

    movement_type = models.CharField(
        max_length=20,
        choices=MOVEMENT_TYPES
    )

    quantity = models.DecimalField(
        max_digits=18,
        decimal_places=4
    )

    unit_cost = models.DecimalField(
        max_digits=18,
        decimal_places=6
    )

    total_cost = models.DecimalField(
        max_digits=18,
        decimal_places=2
    )

    project_partner = models.ForeignKey(
        "partners.ProjectPartner",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        help_text="Required only for contribution"
    )

    journal_entry = models.ForeignKey(
        "journal.JournalEntry",
        on_delete=models.PROTECT,
        related_name="inventory_movements"
    )

    created_by = models.ForeignKey(
        "auth_users.User",
        on_delete=models.PROTECT
    )

    created_at = models.DateTimeField(auto_now_add=True)
```

---

# assets app

---

## Asset


```python
class Asset(models.Model):

    OWNERSHIP_TYPES = [
        ("owned", "Owned by Project"),
        ("partner_contribution", "Partner Contribution"),
    ]

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="assets"
    )

    name = models.CharField(max_length=200)

    serial_number = models.CharField(
        max_length=100,
        blank=True
    )

    ownership_type = models.CharField(
        max_length=30,
        choices=OWNERSHIP_TYPES
    )

    project_partner = models.ForeignKey(
        "partners.ProjectPartner",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        help_text="Required only if contributed by partner"
    )

    purchase_date = models.DateField()

    cost = models.DecimalField(
        max_digits=18,
        decimal_places=2
    )

    useful_life_months = models.IntegerField()

    residual_value = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0
    )

    asset_account = models.ForeignKey(
        "coa.Account",
        on_delete=models.PROTECT,
        related_name="asset_accounts"
    )

    accumulated_depreciation_account = models.ForeignKey(
        "coa.Account",
        on_delete=models.PROTECT,
        related_name="asset_acc_dep_accounts"
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
```

---

# Accounting Logic (Handled in Services)

