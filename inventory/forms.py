from django import forms
from django.utils.translation import gettext_lazy as _

from core.models import Currency
from cash.models import Cashbox
from partners.models import ProjectPartner
from .models import InventoryItem


class InventoryItemForm(forms.Form):
    name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        label=_("Item Name"),
    )
    unit = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "kg, bag, ton, liter…"}),
        label=_("Unit"),
    )


class InventoryPurchaseForm(forms.Form):
    item = forms.ModelChoiceField(
        queryset=InventoryItem.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        label=_("Item"),
    )
    date = forms.DateField(
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        label=_("Date"),
    )
    quantity = forms.DecimalField(
        max_digits=18, decimal_places=4,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.0001", "min": "0"}),
        label=_("Quantity"),
    )
    unit_cost = forms.DecimalField(
        max_digits=18, decimal_places=6,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.000001", "min": "0"}),
        label=_("Unit Cost"),
    )
    cashbox = forms.ModelChoiceField(
        queryset=Cashbox.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        label=_("Paid From"),
    )
    description = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        label=_("Description"),
    )
    use_base_currency = forms.BooleanField(
        required=False,
        initial=True,
        label=_("Base Currency"),
        widget=forms.CheckboxInput(attrs={"class": "form-check-input", "id": "id_use_base_currency"}),
    )
    currency = forms.ModelChoiceField(
        queryset=Currency.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        label=_("Currency"),
    )
    exchange_rate = forms.DecimalField(
        max_digits=18, decimal_places=6, initial=1,
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.000001", "min": "0"}),
        label=_("Exchange Rate"),
    )

    def __init__(self, project, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["item"].queryset = InventoryItem.objects.filter(project=project, is_active=True)
        self.fields["cashbox"].queryset = Cashbox.objects.filter(project=project, is_active=True)


class InventoryConsumptionForm(forms.Form):
    item = forms.ModelChoiceField(
        queryset=InventoryItem.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        label=_("Item"),
    )
    date = forms.DateField(
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        label=_("Date"),
    )
    quantity = forms.DecimalField(
        max_digits=18, decimal_places=4,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.0001", "min": "0"}),
        label=_("Quantity"),
    )
    description = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        label=_("Description"),
    )

    def __init__(self, project, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["item"].queryset = InventoryItem.objects.filter(project=project, is_active=True)

    def clean_quantity(self):
        qty = self.cleaned_data.get("quantity")
        item = self.cleaned_data.get("item")
        if item and qty:
            if qty > item.quantity_on_hand():
                raise forms.ValidationError(
                    _("Quantity exceeds available stock (%(qty)s %(unit)s).") % {
                        "qty": item.quantity_on_hand(),
                        "unit": item.unit,
                    }
                )
        return qty


class InventoryAdjustmentForm(forms.Form):
    DIRECTION = [("increase", _("Increase")), ("decrease", _("Decrease"))]

    item = forms.ModelChoiceField(
        queryset=InventoryItem.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        label=_("Item"),
    )
    date = forms.DateField(
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        label=_("Date"),
    )
    direction = forms.ChoiceField(
        choices=DIRECTION,
        widget=forms.Select(attrs={"class": "form-select"}),
        label=_("Direction"),
    )
    quantity = forms.DecimalField(
        max_digits=18, decimal_places=4,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.0001", "min": "0"}),
        label=_("Quantity"),
    )
    unit_cost = forms.DecimalField(
        max_digits=18, decimal_places=6,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.000001", "min": "0"}),
        label=_("Unit Cost"),
    )
    description = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        label=_("Description"),
    )

    def __init__(self, project, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["item"].queryset = InventoryItem.objects.filter(project=project, is_active=True)


class PartnerInventoryContributionForm(forms.Form):
    item = forms.ModelChoiceField(
        queryset=InventoryItem.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        label=_("Item"),
    )
    project_partner = forms.ModelChoiceField(
        queryset=ProjectPartner.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        label=_("Partner"),
    )
    date = forms.DateField(
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        label=_("Date"),
    )
    quantity = forms.DecimalField(
        max_digits=18, decimal_places=4,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.0001", "min": "0"}),
        label=_("Quantity"),
    )
    unit_cost = forms.DecimalField(
        max_digits=18, decimal_places=6,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.000001", "min": "0"}),
        label=_("Unit Cost"),
    )
    description = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        label=_("Description"),
    )
    use_base_currency = forms.BooleanField(
        required=False,
        initial=True,
        label=_("Base Currency"),
        widget=forms.CheckboxInput(attrs={"class": "form-check-input", "id": "id_use_base_currency"}),
    )
    currency = forms.ModelChoiceField(
        queryset=Currency.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        label=_("Currency"),
    )
    exchange_rate = forms.DecimalField(
        max_digits=18, decimal_places=6, initial=1,
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.000001", "min": "0"}),
        label=_("Exchange Rate"),
    )

    def __init__(self, project, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["item"].queryset = InventoryItem.objects.filter(project=project, is_active=True)
        self.fields["project_partner"].queryset = ProjectPartner.objects.filter(project=project, is_active=True)
