# billing/admin.py

from django.contrib import admin
from .models import (
    Supplier, Product, ProductVariant, StockItem, PurchaseOrder, PurchaseOrderItem,
    SupplierPayment, SupplierRefund, PurchaseReturn, Service, Invoice, InvoiceItem,
    InvoicePayment, Refund, StockAdjustment, StockItemTransaction, ReplacementItem,
    SupplierCredit, CreditApplication
)

# Supplier Admin
@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'contact_person', 'phone_number', 'email')
    search_fields = ('name', 'contact_person', 'phone_number', 'email')

# Product Admin
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'is_stockable', 'is_active')
    list_filter = ('category', 'is_stockable', 'is_active')
    search_fields = ('name',)

# ProductVariant Admin
@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'sku', 'price', 'low_stock_threshold', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('product__name', 'brand', 'variant_description', 'sku')

# StockItem Admin
@admin.register(StockItem)
class StockItemAdmin(admin.ModelAdmin):
    list_display = ('batch_number', 'product_variant', 'quantity', 'cost_price', 'date_received')
    list_filter = ('product_variant', 'supplier', 'expiry_date')
    search_fields = ('batch_number', 'product_variant__product__name', 'supplier__name')

# PurchaseOrder Admin
@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = (
        '__str__', 'supplier', 'order_date', 'status',
        'grand_total_display', 'balance_due_display'
    )
    list_filter = ('status', 'order_date', 'supplier')
    search_fields = ('id', 'supplier__name')
    readonly_fields = (
        'grand_total_display', 'amount_paid_display', 'balance_due_display'
    )

    @admin.display(description='Grand Total')
    def grand_total_display(self, obj):
        return f"₹{obj.grand_total}"

    @admin.display(description='Amount Paid')
    def amount_paid_display(self, obj):
        return f"₹{obj.amount_paid}"

    @admin.display(description='Balance Due')
    def balance_due_display(self, obj):
        return f"₹{obj.balance_due}"

# PurchaseOrderItem Admin
@admin.register(PurchaseOrderItem)
class PurchaseOrderItemAdmin(admin.ModelAdmin):
    list_display = ('purchase_order', 'product_variant', 'quantity', 'quantity_received')
    list_filter = ('purchase_order__status',)
    search_fields = ('purchase_order__id', 'product_variant__product__name')

# SupplierPayment Admin
@admin.register(SupplierPayment)
class SupplierPaymentAdmin(admin.ModelAdmin):
    list_display = ('purchase_order', 'payment_date', 'amount', 'payment_method')
    list_filter = ('payment_method', 'payment_date')
    search_fields = ('purchase_order__id', 'purchase_order__supplier__name')

# SupplierRefund Admin
@admin.register(SupplierRefund)
class SupplierRefundAdmin(admin.ModelAdmin):
    list_display = ('purchase_order', 'refund_date', 'amount')
    list_filter = ('refund_date',)
    search_fields = ('purchase_order__id', 'purchase_order__supplier__name')

# PurchaseReturn Admin
@admin.register(PurchaseReturn)
class PurchaseReturnAdmin(admin.ModelAdmin):
    list_display = ('purchase_order', 'stock_item', 'quantity', 'return_date')
    list_filter = ('return_date',)
    search_fields = ('purchase_order__id', 'stock_item__batch_number')

# ✅ UPDATED: ReplacementItem Admin with correct fields
@admin.register(ReplacementItem)
class ReplacementItemAdmin(admin.ModelAdmin):
    list_display = ('purchase_return', 'quantity', 'date_received')
    list_filter = ('date_received',)
    search_fields = ('purchase_return__stock_item__batch_number',)

# Service Admin
@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)

# Invoice Admin
@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        'invoice_number', 'patient', 'invoice_date', 'status',
        'amount_paid_display', 'balance_due_display', 'total_refunded_display'
    )
    list_filter = ('status', 'invoice_date', 'doctor')
    search_fields = ('invoice_number', 'patient__name')
    readonly_fields = (
        'amount_paid_display', 'balance_due_display', 'total_refunded_display'
    )

    @admin.display(description='Amount Paid')
    def amount_paid_display(self, obj):
        return obj.amount_paid

    @admin.display(description='Balance Due')
    def balance_due_display(self, obj):
        return obj.balance_due

    @admin.display(description='Total Refunded')
    def total_refunded_display(self, obj):
        return obj.total_refunded

# InvoiceItem Admin
@admin.register(InvoiceItem)
class InvoiceItemAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'description', 'quantity', 'unit_price', 'discount')
    list_filter = ('invoice__status',)
    search_fields = ('invoice__invoice_number', 'description')

# InvoicePayment Admin
@admin.register(InvoicePayment)
class InvoicePaymentAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'payment_date', 'amount', 'payment_method')
    list_filter = ('payment_method', 'payment_date')
    search_fields = ('invoice__invoice_number', 'invoice__patient__name')

# Refund Admin
@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'refund_date', 'amount', 'method')
    list_filter = ('method', 'refund_date')
    search_fields = ('invoice__invoice_number', 'invoice__patient__name')

# StockAdjustment Admin
@admin.register(StockAdjustment)
class StockAdjustmentAdmin(admin.ModelAdmin):
    list_display = ('product_variant', 'adjustment_type', 'quantity', 'reason', 'adjustment_date', 'adjusted_by')
    list_filter = ('adjustment_type', 'reason', 'adjustment_date')
    search_fields = ('product_variant__product__name', 'adjusted_by__username')

# StockItemTransaction Admin
@admin.register(StockItemTransaction)
class StockItemTransactionAdmin(admin.ModelAdmin):
    list_display = ('invoice_item', 'stock_item', 'quantity')
    search_fields = ('invoice_item__invoice__invoice_number', 'stock_item__batch_number')

    # SupplierCredit Admin
@admin.register(SupplierCredit)
class SupplierCreditAdmin(admin.ModelAdmin):
    list_display = ('id', 'supplier', 'initial_amount', 'balance', 'date_issued', 'is_fully_used')
    list_filter = ('is_fully_used', 'date_issued', 'supplier')
    search_fields = ('supplier__name', 'source_refund__id')
    readonly_fields = ('initial_amount', 'balance', 'is_fully_used')

# CreditApplication Admin
@admin.register(CreditApplication)
class CreditApplicationAdmin(admin.ModelAdmin):
    list_display = ('credit', 'applied_to_po', 'amount_applied', 'date_applied')
    list_filter = ('date_applied',)
    search_fields = ('credit__supplier__name', 'applied_to_po__id')