# billing/urls.py

from django.urls import path
from . import views

app_name = 'billing'

urlpatterns = [
    # Product and Variant URLs
    path('products/', views.ProductListView.as_view(), name='product_list'),
    path('products/add/', views.ProductCreateView.as_view(), name='product_create'),
    path('products/<int:pk>/', views.ProductDetailView.as_view(), name='product_detail'),
    path('products/<int:pk>/edit/', views.ProductUpdateView.as_view(), name='product_edit'),
    path('products/<int:pk>/delete/', views.ProductDeleteView.as_view(), name='product_delete'),
    path('products/<int:product_pk>/add-variant/', views.variant_create_view, name='variant_create'),
    path('variants/<int:pk>/edit/', views.variant_edit_view, name='variant_edit'),
    path('variants/<int:pk>/delete/', views.variant_delete_view, name='variant_delete'),

    # Inventory and Stock Management URLs
    path('inventory/', views.inventory_list_view, name='inventory_list'),
    path('stock-item/<int:pk>/edit/', views.edit_stock_item_view, name='edit_stock_item'),
    path('stock-adjustments/', views.stock_adjustment_list_view, name='stock_adjustment_list'),
    path('stock-adjustments/create/', views.create_stock_adjustment_view, name='create_stock_adjustment'),

    # Purchase Order URLs
    path('purchase-orders/', views.purchase_order_list_view, name='purchase_order_list'),
    path('purchase-orders/create/', views.create_purchase_order_view, name='create_purchase_order'),
    path('purchase-orders/create/with-variant/<int:pk>/', views.create_purchase_order_view, name='create_purchase_order_with_variant'),
    path('purchase-orders/<int:pk>/', views.purchase_order_detail_view, name='purchase_order_detail'),
    path('purchase-orders/<int:pk>/edit/', views.edit_purchase_order_view, name='edit_purchase_order'),
    path('purchase-orders/<int:pk>/cancel/', views.cancel_purchase_order_view, name='cancel_purchase_order'),
    path('purchase-orders/<int:pk>/receive/', views.receive_purchase_order_view, name='receive_purchase_order'),
    
    # Return, Refund, and Replacement URLs
    path('returns/', views.return_list_view, name='return_list'),
    path('stock-item/<int:stock_item_pk>/return/', views.create_return_view, name='create_return'),
    path('purchase-orders/<int:po_pk>/return/<int:return_pk>/refund/', views.add_supplier_refund_view, name='add_supplier_refund_for_return'),
    path('returns/<int:return_pk>/general-refund/', views.create_general_refund_view, name='add_general_supplier_refund'),
    path('returns/<int:return_pk>/receive-replacement/', views.receive_replacement_view, name='receive_replacement'),

    # Supplier and Payment URLs
    path('suppliers/', views.supplier_list_view, name='supplier_list'),
    path('suppliers/add/', views.add_supplier_view, name='add_supplier'),
    path('suppliers/<int:pk>/edit/', views.edit_supplier_view, name='edit_supplier'),
    path('suppliers/<int:pk>/delete/', views.delete_supplier_view, name='delete_supplier'),
    path('supplier-payments/add/<int:pk>/', views.add_supplier_payment_view, name='add_supplier_payment'),
    path('purchase-orders/<int:po_pk>/apply-credit/', views.apply_supplier_credit_view, name='apply_supplier_credit'),

    # Service URLs
    path('services/', views.service_list_view, name='service_list'),
    path('services/add/', views.add_service_view, name='add_service'),
    path('services/<int:pk>/edit/', views.edit_service_view, name='edit_service'),
    path('services/<int:pk>/delete/', views.delete_service_view, name='delete_service'),

    # Invoice URLs
    path('invoices/', views.invoice_list_view, name='invoice_list'),
    path('invoices/create/', views.create_invoice_view, name='create_invoice'),
    path('invoices/create/from-appointment/<int:pk>/', views.create_invoice_view, name='create_invoice_for_appointment'),
    path('invoices/<int:pk>/', views.invoice_detail_view, name='invoice_detail'),
    path('invoices/<int:pk>/edit/', views.edit_invoice_view, name='edit_invoice'),
    path('invoices/<int:pk>/delete/', views.delete_invoice_view, name='delete_invoice'),
    path('invoices/<int:pk>/print/', views.print_invoice_view, name='print_invoice'),
    path('invoices/<int:pk>/add-payment/', views.add_invoice_payment_view, name='add_invoice_payment'),
    path('invoices/<int:pk>/record-refund/', views.record_refund_view, name='record_refund'),

    # Report URLs
    path('reports/low-stock/', views.low_stock_report_view, name='low_stock_report'),
]