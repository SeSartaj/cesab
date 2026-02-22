from django.urls import path
from . import views

urlpatterns = [
    path("capital-contribution/", views.capital_contribution, name="capital_contribution"),
    path("shareholder-withdrawal/", views.shareholder_withdrawal, name="shareholder_withdrawal"),
    path("vendor-bill/", views.vendor_bill, name="vendor_bill"),
    path("vendor-advance/", views.vendor_advance, name="vendor_advance"),
    path("vendor-payment/", views.vendor_payment, name="vendor_payment"),
    path("vendor-advance-settlement/", views.vendor_advance_settlement, name="vendor_advance_settlement"),
    path("vendor-direct-payment/", views.vendor_direct_payment, name="vendor_direct_payment"),
    path("vendor-refund/", views.vendor_refund, name="vendor_refund"),
    path("cash-expense/", views.cash_expense, name="cash_expense"),
    path("cashbox-transfer/", views.cashbox_transfer, name="cashbox_transfer"),
    path("bank-deposit/", views.bank_deposit, name="bank_deposit"),
    path("project-income/", views.project_income, name="project_income"),
    path("asset-purchase/", views.asset_purchase, name="asset_purchase"),
    path("pay-salary/", views.pay_salary, name="pay_salary"),
    path("manual/", views.manual_je, name="manual_je"),
]
