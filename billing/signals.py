from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.db import transaction
from decimal import Decimal
from .models import (
    InvoiceItem, Invoice, Product, ProductVariant, StockAdjustment, StockItem,
    StockItemTransaction, PurchaseOrderItem, InvoicePayment, Refund, 
    SupplierCredit, SupplierRefund, CreditApplication
)

@receiver(post_save, sender=InvoiceItem)
@receiver(post_delete, sender=InvoiceItem)
def update_invoice_on_item_change(sender, instance, **kwargs):
    if instance.invoice:
        instance.invoice.save()

@transaction.atomic
def update_stock_for_invoice_item(instance, created, deleted=False):
    previous_state = getattr(instance, '_previous_state', None)
    if previous_state and previous_state.get('stock_item'):
        if not instance.stock_item or instance.stock_item.pk != previous_state['stock_item'].pk:
            StockItemTransaction.objects.filter(invoice_item__pk=instance.pk).delete()
    if deleted and instance.stock_item:
        StockItemTransaction.objects.filter(invoice_item=instance).delete()
    if not deleted and instance.stock_item:
        StockItemTransaction.objects.update_or_create(
            invoice_item=instance,
            defaults={'stock_item': instance.stock_item, 'quantity': instance.quantity}
        )

@receiver(pre_save, sender=InvoiceItem)
def cache_previous_invoice_item_state(sender, instance, **kwargs):
    if instance.pk:
        try:
            original = sender.objects.get(pk=instance.pk)
            instance._previous_state = {
                'stock_item': original.stock_item, 'quantity': original.quantity,
            }
        except sender.DoesNotExist:
            instance._previous_state = None

@receiver(post_save, sender=InvoiceItem)
def on_invoice_item_save(sender, instance, created, **kwargs):
    update_stock_for_invoice_item(instance, created)

@receiver(post_delete, sender=InvoiceItem)
def on_invoice_item_delete(sender, instance, **kwargs):
    update_stock_for_invoice_item(instance, created=False, deleted=True)

@receiver(post_save, sender=InvoicePayment)
@receiver(post_delete, sender=InvoicePayment)
def on_payment_change(sender, instance, **kwargs):
    if instance.invoice:
        instance.invoice.save()

@receiver(post_save, sender=Refund)
@receiver(post_delete, sender=Refund)
def on_refund_change(sender, instance, **kwargs):
    if instance.invoice:
        instance.invoice.save()

@receiver(post_save, sender=PurchaseOrderItem)
def update_po_on_item_save(sender, instance, **kwargs):
    if instance.purchase_order:
        instance.purchase_order.update_status()

@receiver(post_save, sender=SupplierRefund)
def create_credit_on_refund(sender, instance, created, **kwargs):
    """
    Automatically creates a SupplierCredit when a SupplierRefund is created.
    """
    if created:
        supplier = None
        if instance.purchase_order and instance.purchase_order.supplier:
            supplier = instance.purchase_order.supplier
        elif instance.purchase_return and instance.purchase_return.stock_item.supplier:
            supplier = instance.purchase_return.stock_item.supplier

        if supplier:
            SupplierCredit.objects.create(
                supplier=supplier,
                source_refund=instance,
                initial_amount=instance.amount,
                balance=instance.amount,
                notes=f"Credit from refund for return #{instance.purchase_return.pk}"
            )

@receiver(post_save, sender=CreditApplication)
def update_credit_balance_on_application(sender, instance, created, **kwargs):
    """
    Automatically updates the balance of a SupplierCredit when a credit is applied.
    """
    if created:
        credit = instance.credit
        credit.balance -= instance.amount_applied

        # Mark as fully used if balance is zero or less
        if credit.balance <= Decimal('0.00'):
            credit.is_fully_used = True
        
        credit.save()