
---

# Updated Apps Structure

```python
inventory/
    InventoryItem
    InventoryMovement

```

---


this is our second iteration in this iteration we need the following:
- add ui for adding partners. we want projects to be isolated, so no global data to be visible to users inside project. for that reason, add ui for adding partner to project dasbhoard, show a form that will create both partner and project partner in one go. leave the user of partner empty. 
- i want to be able to track inventory, how much of items remaining. also add transaction types for inventory maangement. a partner might contribute by bringing inventory instead of cash. handle that as well.
- also add pashto langauge option. 
- in the forms, add a check button which says base currency, it should be checked by default. when it is checked, don't show currency and exchange rate. only show the base currency of the project. if there is a simple way to reuse this logic do it. 
- on the dashboard for shareholders table, which shows remaining, add a progress bar that shows how much contributed. 
- for authorization, make sure you use django model permissions, not role. because each roles permissions might change in the future. 
- on the project dashboard statistics, also show payables, 
- on the url projects/3/vendors/2/ when i click add bill, the vendor-bill form should set the vendor to 2 by default. 
- on the vendors page, add the following options as well:
    -Vendor Advance Settlement
    -Direct Payment
    -Vendor Refund
- for all journal entries allow option to add counter balancing entries to fix errors and mistakes. but user should never be able to delete journal eentry. 
- 


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


# Accounting Logic (Handled in Services)

