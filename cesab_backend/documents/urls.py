from django.urls import path
from . import views

urlpatterns = [
    # Taxes
    path("taxes/", views.tax_list, name="tax_list"),
    path("taxes/add/", views.tax_create, name="tax_create"),
    path("taxes/<int:pk>/edit/", views.tax_edit, name="tax_edit"),

    # Vendor Bills
    path("bills/", views.VendorBillListView.as_view(), name="bill_list"),
    path("bills/add/", views.bill_create, name="bill_create"),
    path("bills/<int:pk>/", views.bill_detail, name="bill_detail"),
    path("bills/<int:pk>/edit/", views.bill_edit, name="bill_edit"),
    path("bills/<int:pk>/post/", views.bill_post, name="bill_post"),
    path("bills/<int:pk>/reverse/", views.bill_reverse, name="bill_reverse"),
    path("bills/<int:pk>/attachments/upload/", views.bill_attachment_upload, name="bill_attachment_upload"),
    path("bills/<int:pk>/attachments/<int:att_pk>/delete/", views.bill_attachment_delete, name="bill_attachment_delete"),

    # Customer Invoices
    path("invoices/", views.CustomerInvoiceListView.as_view(), name="invoice_list"),
    path("invoices/add/", views.invoice_create, name="invoice_create"),
    path("invoices/<int:pk>/", views.invoice_detail, name="invoice_detail"),
    path("invoices/<int:pk>/edit/", views.invoice_edit, name="invoice_edit"),
    path("invoices/<int:pk>/post/", views.invoice_post, name="invoice_post"),
    path("invoices/<int:pk>/reverse/", views.invoice_reverse, name="invoice_reverse"),
    path("invoices/<int:pk>/attachments/upload/", views.invoice_attachment_upload, name="invoice_attachment_upload"),
    path("invoices/<int:pk>/attachments/<int:att_pk>/delete/", views.invoice_attachment_delete, name="invoice_attachment_delete"),

    # Payments (vendor)
    path("payments/", views.PaymentListView.as_view(), name="payment_list"),
    path("payments/add/", views.payment_create, name="payment_create"),
    path("payments/<int:pk>/", views.payment_detail, name="payment_detail"),
    path("payments/<int:pk>/edit/", views.payment_edit, name="payment_edit"),
    path("payments/<int:pk>/post/", views.payment_post, name="payment_post"),
    path("payments/<int:pk>/reverse/", views.payment_reverse, name="payment_reverse"),

    # Receipts (customer)
    path("receipts/", views.ReceiptListView.as_view(), name="receipt_list"),
    path("receipts/add/", views.receipt_create, name="receipt_create"),
    path("receipts/<int:pk>/", views.receipt_detail, name="receipt_detail"),
    path("receipts/<int:pk>/edit/", views.receipt_edit, name="receipt_edit"),
    path("receipts/<int:pk>/post/", views.receipt_post, name="receipt_post"),
    path("receipts/<int:pk>/reverse/", views.receipt_reverse, name="receipt_reverse"),
]
