from django import forms
from django.utils.translation import gettext_lazy as _
from django.forms import inlineformset_factory

from core.models import Currency
from cash.models import Cashbox
from coa.models import Account
from vendors.models import Contact
from .models import Tax, VendorBill, VendorBillLine, CustomerInvoice, CustomerInvoiceLine, Payment, Receipt


class CashboxSelectWidget(forms.Select):
    """Select widget that injects data-currency-id on each cashbox <option> for JS filtering."""

    def __init__(self, *args, cashbox_map=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._cashbox_map = cashbox_map or {}

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        if value:
            try:
                currency_id = self._cashbox_map.get(int(str(value)))
                if currency_id:
                    option["attrs"]["data-currency-id"] = str(currency_id)
            except (ValueError, TypeError):
                pass
        return option


class CurrencySelectWidget(forms.Select):
    """Select widget that injects data-code and data-rate on each currency <option>."""

    def __init__(self, *args, currency_map=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._currency_map = currency_map or {}  # {pk: (code, rate_bc)}

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        if value:
            try:
                info = self._currency_map.get(int(str(value)))
                if info:
                    option["attrs"]["data-code"] = info["code"]
                    option["attrs"]["data-id"]   = str(info["id"])
            except (ValueError, TypeError):
                pass
        return option


class TaxSelectWidget(forms.Select):
    """Select widget that injects data-rate on each tax <option> for JS totals."""

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        if value:
            try:
                option["attrs"]["data-rate"] = str(Tax.objects.get(pk=value).rate)
            except (Tax.DoesNotExist, ValueError, TypeError):
                pass
        return option


class TaxForm(forms.ModelForm):
    class Meta:
        model = Tax
        fields = ["name", "rate", "account", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "rate": forms.NumberInput(attrs={"class": "form-control", "step": "0.0001", "min": "0", "max": "1"}),
            "account": forms.Select(attrs={"class": "form-select"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, project, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = Account.objects.filter(
            project=project, is_active=True, is_tax_account=True
        )


class VendorBillForm(forms.ModelForm):
    class Meta:
        model = VendorBill
        fields = ["contact", "date", "due_date", "currency", "exchange_rate", "notes"]
        widgets = {
            "contact": forms.Select(attrs={"class": "form-select"}),
            "date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "due_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "currency": forms.Select(attrs={"class": "form-select", "id": "id_currency"}),
            "exchange_rate": forms.NumberInput(attrs={"class": "form-control", "step": "0.000001", "min": "0"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

    def __init__(self, project, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["contact"].queryset = Contact.objects.filter(
            project=project, is_active=True,
            contact_type__in=[Contact.VENDOR, Contact.BOTH],
        )
        self.fields["currency"].queryset = Currency.objects.filter(is_active=True)
        self.fields["currency"].initial = project.base_currency
        self.fields["exchange_rate"].initial = 1


class VendorBillLineForm(forms.ModelForm):
    class Meta:
        model = VendorBillLine
        fields = ["description", "account", "quantity", "unit_price", "tax"]
        widgets = {
            "description": forms.TextInput(attrs={"class": "form-control"}),
            "account": forms.Select(attrs={"class": "form-select"}),
            "quantity": forms.NumberInput(attrs={"class": "form-control", "step": "0.0001", "min": "0"}),
            "unit_price": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "tax": TaxSelectWidget(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        if project is not None:
            self.fields["account"].queryset = Account.objects.filter(
                project=project, account_type="expense", is_active=True
            )
            self.fields["tax"].queryset = Tax.objects.filter(project=project, is_active=True)
        self.fields["tax"].required = False


def make_bill_line_formset(project, extra=1):
    FormSet = inlineformset_factory(
        VendorBill, VendorBillLine,
        form=VendorBillLineForm,
        extra=extra, can_delete=True,
    )

    class ProjectBoundFormSet(FormSet):
        def get_form_kwargs(self, index):
            kwargs = super().get_form_kwargs(index)
            kwargs["project"] = project
            return kwargs

    return ProjectBoundFormSet


class CustomerInvoiceForm(forms.ModelForm):
    class Meta:
        model = CustomerInvoice
        fields = ["contact", "date", "due_date", "currency", "exchange_rate", "notes"]
        widgets = {
            "contact": forms.Select(attrs={"class": "form-select"}),
            "date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "due_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "currency": forms.Select(attrs={"class": "form-select", "id": "id_currency"}),
            "exchange_rate": forms.NumberInput(attrs={"class": "form-control", "step": "0.000001", "min": "0"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

    def __init__(self, project, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["contact"].queryset = Contact.objects.filter(
            project=project, is_active=True,
            contact_type__in=[Contact.CUSTOMER, Contact.BOTH],
        )
        self.fields["currency"].queryset = Currency.objects.filter(is_active=True)
        self.fields["currency"].initial = project.base_currency
        self.fields["exchange_rate"].initial = 1


class CustomerInvoiceLineForm(forms.ModelForm):
    class Meta:
        model = CustomerInvoiceLine
        fields = ["description", "account", "quantity", "unit_price", "tax"]
        widgets = {
            "description": forms.TextInput(attrs={"class": "form-control"}),
            "account": forms.Select(attrs={"class": "form-select"}),
            "quantity": forms.NumberInput(attrs={"class": "form-control", "step": "0.0001", "min": "0"}),
            "unit_price": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "tax": TaxSelectWidget(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        if project is not None:
            self.fields["account"].queryset = Account.objects.filter(
                project=project, account_type="income", is_active=True
            )
            self.fields["tax"].queryset = Tax.objects.filter(project=project, is_active=True)
        self.fields["tax"].required = False


def make_invoice_line_formset(project, extra=1):
    FormSet = inlineformset_factory(
        CustomerInvoice, CustomerInvoiceLine,
        form=CustomerInvoiceLineForm,
        extra=extra, can_delete=True,
    )

    class ProjectBoundFormSet(FormSet):
        def get_form_kwargs(self, index):
            kwargs = super().get_form_kwargs(index)
            kwargs["project"] = project
            return kwargs

    return ProjectBoundFormSet


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["contact", "date", "currency", "exchange_rate", "amount", "cashbox", "bill", "notes"]
        widgets = {
            "contact": forms.Select(attrs={"class": "form-select"}),
            "date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "currency": forms.Select(attrs={"class": "form-select"}),
            "exchange_rate": forms.NumberInput(attrs={"class": "form-control", "step": "0.000001", "min": "0"}),
            "amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "bill": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

    def __init__(self, project, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["contact"].queryset = Contact.objects.filter(
            project=project, is_active=True,
            contact_type__in=[Contact.VENDOR, Contact.BOTH],
        )
        currencies_qs = Currency.objects.filter(is_active=True)
        currency_map = {c.pk: {"code": c.code, "id": c.pk} for c in currencies_qs}
        self.fields["currency"].widget = CurrencySelectWidget(
            currency_map=currency_map, attrs={"class": "form-select"}
        )
        self.fields["currency"].queryset = currencies_qs
        self.fields["currency"].initial = project.base_currency
        self.fields["exchange_rate"].initial = 1
        cashboxes_qs = Cashbox.objects.filter(project=project, is_active=True)
        cashbox_map = {cb.pk: cb.currency_id for cb in cashboxes_qs}
        self.fields["cashbox"].widget = CashboxSelectWidget(
            cashbox_map=cashbox_map, attrs={"class": "form-select"}
        )
        self.fields["cashbox"].queryset = cashboxes_qs
        self.fields["bill"].queryset = VendorBill.objects.filter(
            project=project, status="posted"
        )
        self.fields["bill"].required = False


class ReceiptForm(forms.ModelForm):
    class Meta:
        model = Receipt
        fields = ["contact", "income_account", "date", "currency", "exchange_rate", "amount", "cashbox", "invoice", "notes"]
        widgets = {
            "contact": forms.Select(attrs={"class": "form-select"}),
            "income_account": forms.Select(attrs={"class": "form-select"}),
            "date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "currency": forms.Select(attrs={"class": "form-select"}),
            "exchange_rate": forms.NumberInput(attrs={"class": "form-control", "step": "0.000001", "min": "0"}),
            "amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "invoice": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

    def __init__(self, project, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["contact"].queryset = Contact.objects.filter(
            project=project, is_active=True,
            contact_type__in=[Contact.CUSTOMER, Contact.BOTH],
        )
        self.fields["contact"].required = False
        self.fields["income_account"].queryset = Account.objects.filter(
            project=project, account_type="income", is_active=True,
        )
        self.fields["income_account"].required = False
        self.fields["income_account"].label = _("Income Account (walk-in)")
        currencies_qs = Currency.objects.filter(is_active=True)
        currency_map = {c.pk: {"code": c.code, "id": c.pk} for c in currencies_qs}
        self.fields["currency"].widget = CurrencySelectWidget(
            currency_map=currency_map, attrs={"class": "form-select"}
        )
        self.fields["currency"].queryset = currencies_qs
        self.fields["currency"].initial = project.base_currency
        self.fields["exchange_rate"].initial = 1
        cashboxes_qs = Cashbox.objects.filter(project=project, is_active=True)
        cashbox_map = {cb.pk: cb.currency_id for cb in cashboxes_qs}
        self.fields["cashbox"].widget = CashboxSelectWidget(
            cashbox_map=cashbox_map, attrs={"class": "form-select"}
        )
        self.fields["cashbox"].queryset = cashboxes_qs
        self.fields["invoice"].queryset = CustomerInvoice.objects.filter(
            project=project, status="posted"
        )
        self.fields["invoice"].required = False

    def clean(self):
        cleaned = super().clean()
        contact = cleaned.get("contact")
        income_account = cleaned.get("income_account")
        if not contact and not income_account:
            raise forms.ValidationError(
                _("Either select a customer or choose an income account for this walk-in receipt.")
            )
        if contact and income_account:
            raise forms.ValidationError(
                _("Select either a customer or an income account, not both.")
            )
        return cleaned


class ReverseDocumentForm(forms.Form):
    date = forms.DateField(
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        label=_("Reversal Date"),
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        label=_("Notes"),
    )
