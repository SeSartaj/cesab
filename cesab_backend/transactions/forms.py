from django import forms
from django.utils.translation import gettext_lazy as _
from core.models import Currency
from cash.models import Cashbox
from partners.models import ProjectPartner
from vendors.models import Vendor
from employees.models import ProjectEmployee
from coa.models import Account


class BaseTxForm(forms.Form):
    """Base transaction form. Includes a 'use_base_currency' toggle that hides currency/rate fields."""
    date = forms.DateField(
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        label=_("Date"),
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


class CapitalContributionForm(BaseTxForm):
    project_partner = forms.ModelChoiceField(
        queryset=ProjectPartner.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        label=_("Partner"),
    )
    amount = forms.DecimalField(
        max_digits=18, decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
        label=_("Amount"),
    )
    cashbox = forms.ModelChoiceField(
        queryset=Cashbox.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        label=_("Cashbox"),
    )

    def __init__(self, project, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["project_partner"].queryset = ProjectPartner.objects.filter(project=project, is_active=True)
        self.fields["cashbox"].queryset = Cashbox.objects.filter(project=project, is_active=True)


class ShareholderWithdrawalForm(BaseTxForm):
    project_partner = forms.ModelChoiceField(
        queryset=ProjectPartner.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        label=_("Partner"),
    )
    amount = forms.DecimalField(
        max_digits=18, decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
        label=_("Amount"),
    )
    cashbox = forms.ModelChoiceField(
        queryset=Cashbox.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        label=_("Cashbox"),
    )

    def __init__(self, project, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["project_partner"].queryset = ProjectPartner.objects.filter(project=project, is_active=True)
        self.fields["cashbox"].queryset = Cashbox.objects.filter(project=project, is_active=True)


class VendorBillForm(BaseTxForm):
    vendor = forms.ModelChoiceField(
        queryset=Vendor.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        label=_("Vendor"),
    )
    expense_account = forms.ModelChoiceField(
        queryset=Account.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        label=_("Expense Account"),
    )
    amount = forms.DecimalField(
        max_digits=18, decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
        label=_("Amount"),
    )

    def __init__(self, project, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["vendor"].queryset = Vendor.objects.filter(project=project, is_active=True)
        self.fields["expense_account"].queryset = Account.objects.filter(
            project=project, account_type="expense", is_active=True
        )


class VendorAdvanceForm(BaseTxForm):
    vendor = forms.ModelChoiceField(
        queryset=Vendor.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        label=_("Vendor"),
    )
    amount = forms.DecimalField(
        max_digits=18, decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
        label=_("Amount"),
    )
    cashbox = forms.ModelChoiceField(
        queryset=Cashbox.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        label=_("Cashbox"),
    )

    def __init__(self, project, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["vendor"].queryset = Vendor.objects.filter(project=project, is_active=True)
        self.fields["cashbox"].queryset = Cashbox.objects.filter(project=project, is_active=True)


class VendorPaymentForm(BaseTxForm):
    vendor = forms.ModelChoiceField(
        queryset=Vendor.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        label=_("Vendor"),
    )
    amount = forms.DecimalField(
        max_digits=18, decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
        label=_("Amount"),
    )
    cashbox = forms.ModelChoiceField(
        queryset=Cashbox.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        label=_("Cashbox"),
    )

    def __init__(self, project, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["vendor"].queryset = Vendor.objects.filter(project=project, is_active=True)
        self.fields["cashbox"].queryset = Cashbox.objects.filter(project=project, is_active=True)


class CashExpenseForm(BaseTxForm):
    expense_account = forms.ModelChoiceField(
        queryset=Account.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        label=_("Expense Account"),
    )
    amount = forms.DecimalField(
        max_digits=18, decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
        label=_("Amount"),
    )
    cashbox = forms.ModelChoiceField(
        queryset=Cashbox.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        label=_("Cashbox"),
    )

    def __init__(self, project, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["expense_account"].queryset = Account.objects.filter(
            project=project, account_type="expense", is_active=True
        )
        self.fields["cashbox"].queryset = Cashbox.objects.filter(project=project, is_active=True)


class CashboxTransferForm(BaseTxForm):
    from_cashbox = forms.ModelChoiceField(
        queryset=Cashbox.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        label=_("From Cashbox"),
    )
    to_cashbox = forms.ModelChoiceField(
        queryset=Cashbox.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        label=_("To Cashbox"),
    )
    amount = forms.DecimalField(
        max_digits=18, decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
        label=_("Amount"),
    )

    def __init__(self, project, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["from_cashbox"].queryset = Cashbox.objects.filter(project=project, is_active=True)
        self.fields["to_cashbox"].queryset = Cashbox.objects.filter(project=project, is_active=True)


class BankDepositForm(CashboxTransferForm):
    pass


class ProjectIncomeForm(BaseTxForm):
    cashbox = forms.ModelChoiceField(
        queryset=Cashbox.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        label=_("Cashbox"),
    )
    amount = forms.DecimalField(
        max_digits=18, decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
        label=_("Amount"),
    )

    def __init__(self, project, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cashbox"].queryset = Cashbox.objects.filter(project=project, is_active=True)


class AssetPurchaseForm(BaseTxForm):
    asset_account = forms.ModelChoiceField(
        queryset=Account.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        label=_("Asset Account"),
    )
    amount = forms.DecimalField(
        max_digits=18, decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
        label=_("Amount"),
    )
    cashbox = forms.ModelChoiceField(
        queryset=Cashbox.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        label=_("Cashbox"),
    )

    def __init__(self, project, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["asset_account"].queryset = Account.objects.filter(
            project=project, account_type="asset", is_active=True
        )
        self.fields["cashbox"].queryset = Cashbox.objects.filter(project=project, is_active=True)


class PaySalaryForm(BaseTxForm):
    employee = forms.ModelChoiceField(
        queryset=ProjectEmployee.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        label=_("Employee"),
    )
    days_or_months = forms.DecimalField(
        max_digits=6, decimal_places=2, initial=1,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
        label=_("Days / Months"),
    )
    cashbox = forms.ModelChoiceField(
        queryset=Cashbox.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        label=_("Cashbox"),
    )

    def __init__(self, project, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["employee"].queryset = ProjectEmployee.objects.filter(project=project, is_active=True)
        self.fields["cashbox"].queryset = Cashbox.objects.filter(project=project, is_active=True)


class ManualJEForm(forms.Form):
    date = forms.DateField(
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        label=_("Date"),
    )
    description = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-control"}),
        label=_("Description"),
    )


class VendorAdvanceSettlementForm(BaseTxForm):
    """Settle vendor advance against outstanding payable."""
    vendor = forms.ModelChoiceField(
        queryset=Vendor.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        label=_("Vendor"),
    )
    amount = forms.DecimalField(
        max_digits=18, decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
        label=_("Settlement Amount"),
    )

    def __init__(self, project, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["vendor"].queryset = Vendor.objects.filter(project=project, is_active=True)


class VendorDirectPaymentForm(BaseTxForm):
    """Pay vendor directly (no bill required) — treated as an expense."""
    vendor = forms.ModelChoiceField(
        queryset=Vendor.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        label=_("Vendor"),
    )
    expense_account = forms.ModelChoiceField(
        queryset=Account.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        label=_("Expense Account"),
    )
    amount = forms.DecimalField(
        max_digits=18, decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
        label=_("Amount"),
    )
    cashbox = forms.ModelChoiceField(
        queryset=Cashbox.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        label=_("Paid From"),
    )

    def __init__(self, project, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["vendor"].queryset = Vendor.objects.filter(project=project, is_active=True)
        self.fields["expense_account"].queryset = Account.objects.filter(
            project=project, account_type="expense", is_active=True
        )
        self.fields["cashbox"].queryset = Cashbox.objects.filter(project=project, is_active=True)


class VendorRefundForm(BaseTxForm):
    """Vendor refunds money back to a cashbox."""
    vendor = forms.ModelChoiceField(
        queryset=Vendor.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        label=_("Vendor"),
    )
    amount = forms.DecimalField(
        max_digits=18, decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
        label=_("Refund Amount"),
    )
    cashbox = forms.ModelChoiceField(
        queryset=Cashbox.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        label=_("Received Into"),
    )

    def __init__(self, project, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["vendor"].queryset = Vendor.objects.filter(project=project, is_active=True)
        self.fields["cashbox"].queryset = Cashbox.objects.filter(project=project, is_active=True)
