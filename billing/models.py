# billing/models.py

from decimal import Decimal
import uuid

from django.conf import settings
from django.core.validators import MinValueValidator, ValidationError
from django.db import models, transaction
from django.db.models import Sum, F, Q, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from phonenumber_field.modelfields import PhoneNumberField


# ========== Supplier ==========

class Supplier(models.Model):
    SUPPLIER_CATEGORY_CHOICES = [
        ('LOCAL_SHOP', 'Local Shop'),
        ('LOCAL_DISTRIBUTOR', 'Local Distributor'),
        ('E_COMMERCE', 'E-Commerce'),
        ('PHARMACEUTICAL', 'Pharmaceutical'),
    ]
    name = models.CharField(max_length=200, unique=True)
    category = models.CharField(max_length=20, choices=SUPPLIER_CATEGORY_CHOICES)
    contact_person = models.CharField(max_length=100, blank=True, null=True)
    phone_number = PhoneNumberField(blank=True, null=True, unique=True)
    email = models.EmailField(blank=True, null=True, unique=True)
    address = models.TextField(blank=True, null=True)

    def get_outstanding_balance(self):
        """
        Calculates the total outstanding balance by summing the balance_due 
        of all purchase orders associated with this supplier.
        """
        # The 'purchase_orders' related_name comes from the ForeignKey in the PurchaseOrder model
        return sum(po.balance_due for po in self.purchase_orders.all())

    class Meta:
        verbose_name = "Supplier"
        verbose_name_plural = "Suppliers"
        ordering = ['name']

    def __str__(self):
        return self.name


# ========== Product & Variants ==========

class Product(models.Model):
    PRODUCT_CATEGORY_CHOICES = [
        ('CONSUMABLES', 'Consumables'),
        ('DENTAL_PRODUCTS', 'Dental Products'),
        ('DENTAL_MATERIALS', 'Dental Materials'),
        ('DENTAL_INSTRUMENTS', 'Dental Instruments'),
        ('DRUGS', 'Drugs'),
        ('ELECTRONICS', 'Electronics'),
        ('MACHINERIES', 'Machineries'),
        ('LAB_SUPPLIES', 'Lab Supplies'),
        ('FURNITURE_FIXTURES', 'Furniture & Fixtures'),
        ('WASTE_MANAGEMENT', 'Waste Management Systems'),
        ('MISCELLANEOUS', 'Miscellaneous'),
    ]
    name = models.CharField(max_length=200, unique=True)
    category = models.CharField(max_length=25, choices=PRODUCT_CATEGORY_CHOICES)
    description = models.TextField(blank=True, null=True)
    is_stockable = models.BooleanField(default=True)
    requires_expiry_tracking = models.BooleanField(
        default=True,
        help_text="Check this if variants of this product have an expiry date (e.g., drugs, materials)."
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = "Product"
        verbose_name_plural = "Products"

    def __str__(self):
        return self.name


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    variant_description = models.CharField(max_length=255, blank=True)
    brand = models.CharField(max_length=100, blank=True, null=True)
    sku = models.CharField(max_length=100, unique=True, null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    low_stock_threshold = models.PositiveIntegerField(default=10)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['product__name', 'brand', 'variant_description']
        unique_together = ('product', 'brand', 'variant_description')
        verbose_name = "Product Variant"
        verbose_name_plural = "Product Variants"

    def __str__(self):
        parts = [self.product.name]
        if self.brand:
            parts.append(self.brand)
        if self.variant_description:
            parts.append(self.variant_description)
        return " - ".join(parts)

    @property
    def stock_quantity(self):
        stock_items = self.stock_items.all()
        total_available = sum(item.quantity_available for item in stock_items)
        return total_available


# ========== StockItem ==========

class StockItem(models.Model):
    SOURCE_CHOICES = [
        ('PURCHASE_ORDER', 'Purchase Order'),
        ('REPLACEMENT', 'Replacement'),
        ('MANUAL_ADDITION', 'Manual Addition'),
    ]
    product_variant = models.ForeignKey(ProductVariant, on_delete=models.PROTECT, related_name='stock_items')
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True, related_name='stock_items')
    purchase_order_item = models.ForeignKey(
        'PurchaseOrderItem', on_delete=models.SET_NULL, null=True, blank=True, related_name='received_batches'
    )
    batch_number = models.CharField(max_length=100)
    expiry_date = models.DateField(null=True, blank=True)
    quantity = models.PositiveIntegerField(verbose_name="Received Quantity")
    mrp = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    base_cost_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    gst_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    date_received = models.DateTimeField(default=timezone.now)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='PURCHASE_ORDER')

    class Meta:
        ordering = ['expiry_date', 'date_received']
        verbose_name = "Stock Item"
        verbose_name_plural = "Stock Items"

    def __str__(self):
        expiry_str = f"Exp: {self.expiry_date.strftime('%b %Y')}" if self.expiry_date else "No Expiry"
        return f"Batch: {self.batch_number} | Avail: {self.quantity_available} | {expiry_str}"

    @property
    def discount_amount(self):
        return (self.base_cost_price * self.quantity * (self.discount_percentage / Decimal('100.00'))).quantize(Decimal('0.01'))

    @property
    def total_cost(self):
        return (self.quantity * self.cost_price).quantize(Decimal('0.01'))

    @property
    def quantity_sold(self):
        return self.transactions.aggregate(total=Coalesce(Sum('quantity'), Value(0)))['total']

    @property
    def quantity_returned(self):
        return self.purchasereturn_set.aggregate(total=Coalesce(Sum('quantity'), 0))['total']

    @property
    def quantity_replaced(self):
        return self.purchasereturn_set.aggregate(total=Coalesce(Sum('replacementitem__quantity'), 0))['total']

    @property
    def total_refunded_amount(self):
        return self.purchasereturn_set.aggregate(
            total=Coalesce(Sum('supplierrefund_set__amount'), Decimal('0.00'))
        )['total']

    @property
    def quantity_available(self):
        return self.quantity - self.quantity_sold - self.quantity_returned

    def clean(self):
        if not self.batch_number.strip():
            raise ValidationError({'batch_number': "Batch number is required."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


# ========== PurchaseOrderItem ==========

class PurchaseOrderItem(models.Model):
    purchase_order = models.ForeignKey('PurchaseOrder', on_delete=models.CASCADE, related_name='items')
    product_variant = models.ForeignKey(ProductVariant, on_delete=models.PROTECT, related_name='purchase_order_items')
    quantity = models.PositiveIntegerField()
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    quantity_received = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.quantity} x {self.product_variant}"

    @property
    def is_fully_received(self):
        return self.quantity_received >= self.quantity

    @property
    def quantity_remaining(self):
        return self.quantity - self.quantity_received


# ========== StockAdjustment ==========

class StockAdjustment(models.Model):
    ADJUSTMENT_TYPE_CHOICES = [
        ('ADDITION', 'Manual Addition'),
        ('SUBTRACTION', 'Manual Subtraction'),
    ]
    REASON_CHOICES = [
        ('DAMAGED', 'Damaged Goods'),
        ('EXPIRED', 'Expired Stock'),
        ('STOCK_TAKE', 'Stock Take Correction'),
        ('INITIAL_STOCK', 'Initial Stock Setup'),
        ('OTHER', 'Other'),
    ]

    product_variant = models.ForeignKey(
        ProductVariant, on_delete=models.PROTECT, related_name='adjustments', null=True, blank=True
    )
    adjustment_type = models.CharField(max_length=11, choices=ADJUSTMENT_TYPE_CHOICES)
    quantity = models.PositiveIntegerField()
    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    notes = models.TextField(blank=True)
    adjustment_date = models.DateTimeField(default=timezone.now)
    adjusted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='stock_adjustments')

    class Meta:
        ordering = ['-adjustment_date']


# ========== Service ==========

class Service(models.Model):
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = "Service"
        verbose_name_plural = "Services"

    def __str__(self):
        return self.name


# ========== StockItemTransaction ==========

class StockItemTransaction(models.Model):
    invoice_item = models.OneToOneField('InvoiceItem', on_delete=models.CASCADE, related_name='stock_transaction')
    stock_item = models.ForeignKey(StockItem, on_delete=models.PROTECT, related_name='transactions')
    quantity = models.PositiveIntegerField()


# ========== Invoice ==========

class Invoice(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PENDING', 'Pending'),
        ('PAID', 'Paid'),
        ('PARTIAL', 'Partial Payment'),
        ('CANCELLED', 'Cancelled'),
    ]

    patient = models.ForeignKey('patients.Patient', on_delete=models.PROTECT, related_name='invoices')
    doctor = models.ForeignKey(
        'staff.StaffMember', on_delete=models.PROTECT, null=True, blank=True,
        limit_choices_to={'user__groups__name': 'Doctors'}, related_name='invoices'
    )
    appointment = models.OneToOneField('appointments.Appointment', on_delete=models.SET_NULL, null=True, blank=True, related_name='invoice')
    invoice_number = models.CharField(max_length=50, unique=True, editable=False)
    invoice_date = models.DateField(default=timezone.now)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='DRAFT')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-invoice_date', '-created_at']
        verbose_name = "Invoice"
        verbose_name_plural = "Invoices"

    def __str__(self):
        return f"Invoice {self.invoice_number} for {self.patient.name} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if not self.invoice_number:
                today_str = timezone.now().strftime('%y%m%d')
                prefix = f'INV-{today_str}-'
                last = Invoice.objects.select_for_update()\
                    .filter(invoice_number__startswith=prefix)\
                    .order_by('invoice_number')\
                    .last()
                seq = int(last.invoice_number.replace(prefix, '')) + 1 if last and last.invoice_number.replace(prefix, '').isdigit() else 1
                self.invoice_number = f'{prefix}{str(seq).zfill(4)}'

            if self.pk:
                self.total_amount = self.calculate_total_amount()
                if self.status != 'CANCELLED':
                    paid = self.payments.aggregate(total=Coalesce(Sum('amount'), Decimal('0.00')))['total'] or Decimal('0.00')
                    refunded = self.refunds.aggregate(total=Coalesce(Sum('amount'), Decimal('0.00')))['total'] or Decimal('0.00')
                    balance = (self.net_amount - paid + refunded).quantize(Decimal('0.01'))
                    if balance <= Decimal('0.00'):
                        self.status = 'PAID'
                    elif paid > Decimal('0.00'):
                        self.status = 'PARTIAL'
                    else:
                        self.status = 'PENDING'

            super().save(*args, **kwargs)

    def calculate_total_amount(self) -> Decimal:
        agg = self.invoice_items.aggregate(
            total=Coalesce(
                Sum(F('quantity') * Coalesce(F('unit_price'), Decimal('0.00'))),
                Decimal('0.00')
            )
        )
        return (agg['total'] or Decimal('0.00')).quantize(Decimal('0.01'))

    @property
    def total_discount(self) -> Decimal:
        items_disc = self.invoice_items.aggregate(
            total=Coalesce(Sum(F('discount') * F('quantity')), Decimal('0.00'))
        )['total'] or Decimal('0.00')
        return (items_disc + (self.discount or Decimal('0.00'))).quantize(Decimal('0.01'))

    @property
    def net_amount(self) -> Decimal:
        return (self.total_amount - self.total_discount).quantize(Decimal('0.01'))

    @property
    def amount_paid(self) -> Decimal:
        return (self.payments.aggregate(total=Coalesce(Sum('amount'), Decimal('0.00')))['total'] or Decimal('0.00')).quantize(Decimal('0.01'))

    @property
    def total_refunded(self) -> Decimal:
        return (self.refunds.aggregate(total=Coalesce(Sum('amount'), Decimal('0.00')))['total'] or Decimal('0.00')).quantize(Decimal('0.01'))

    @property
    def balance_due(self) -> Decimal:
        return (self.net_amount - self.amount_paid + self.total_refunded).quantize(Decimal('0.01'))


# ========== InvoiceItem ==========

class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='invoice_items')
    service = models.ForeignKey(Service, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoice_items')
    stock_item = models.ForeignKey(StockItem, on_delete=models.PROTECT, null=True, blank=True, related_name='invoice_items')
    description = models.CharField(max_length=255, blank=True, default='')
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Invoice Item"
        verbose_name_plural = "Invoice Items"

    def __str__(self):
        desc = self.description or self.service or self.stock_item
        return f"{self.quantity} x {desc} on Invoice {self.invoice.invoice_number}"
    
    @property
    def display_description(self):
        if self.description:
            return self.description
        if self.service:
            return self.service.name
        if self.stock_item:
            return str(self.stock_item.product_variant)
        return "N/A"

    @property
    def net_price(self):
        unit_price = self.unit_price or Decimal('0.00')
        discount = self.discount or Decimal('0.00')
        return (self.quantity * (unit_price - discount)).quantize(Decimal('0.01'))

    def clean(self):
        if self.quantity <= 0:
            raise ValidationError({'quantity': 'Quantity must be at least 1.'})
        if not self.unit_price:
            if self.stock_item:
                self.unit_price = self.stock_item.product_variant.price
            elif self.service:
                self.unit_price = self.service.price
            else:
                self.unit_price = Decimal('0.00')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


# ========== InvoicePayment ==========

class InvoicePayment(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    payment_date = models.DateTimeField(default=timezone.now)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    PAYMENT_METHODS = [
        ('CASH', 'Cash'), ('UPI', 'UPI'), ('BANK', 'Bank Transfer'),
        ('CHEQUE', 'Cheque'), ('CREDIT_CARD', 'Credit Card'),
        ('AMAZON_PAY', 'Amazon Pay Balance'), ('OTHER', 'Other'),
    ]
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='CASH')
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-payment_date']


# ========== Refund ==========

class Refund(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='refunds')
    refund_date = models.DateTimeField(default=timezone.now)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    method = models.CharField(max_length=20, choices=InvoicePayment.PAYMENT_METHODS, default='BANK')
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-refund_date']


# ========== PurchaseOrder ==========
class PurchaseOrder(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PARTIALLY_RECEIVED', 'Partially Received'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='purchase_orders')
    order_date = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-order_date']

    def __str__(self):
        return f"PO #{self.pk} for {self.supplier.name} on {self.order_date.date()}"

    def _get_all_related_returns(self):
        """
        Finds all PurchaseReturn objects related to this PO, including those
        from subsequent replacement batches (nested returns).
        """
        direct_returns = list(self.returns.all().select_related('stock_item'))
        all_returns = list(direct_returns)
        returns_to_check = list(direct_returns)
        processed_return_pks = {r.pk for r in direct_returns}
        while returns_to_check:
            replacements = ReplacementItem.objects.filter(purchase_return__in=returns_to_check).select_related('created_stock_item')
            if not replacements: break
            replacement_stock_items = [rep.created_stock_item for rep in replacements if rep.created_stock_item]
            if not replacement_stock_items: break
            nested_returns = PurchaseReturn.objects.filter(stock_item__in=replacement_stock_items).exclude(pk__in=processed_return_pks).select_related('stock_item')
            newly_found_returns = []
            for nr in nested_returns:
                if nr.pk not in processed_return_pks:
                    all_returns.append(nr)
                    newly_found_returns.append(nr)
                    processed_return_pks.add(nr.pk)
            returns_to_check = newly_found_returns
            if not returns_to_check: break
        return all_returns

    @property
    def grand_total(self):
        total = StockItem.objects.filter(purchase_order_item__purchase_order=self).aggregate(
            total_value=Coalesce(Sum(F('quantity') * F('cost_price')), Decimal('0.00'))
        )['total_value']
        return total.quantize(Decimal('0.01'))

    @property
    def amount_paid(self):
        return (self.payments.aggregate(total=Coalesce(Sum('amount'), Decimal('0.00')))['total'] or Decimal('0.00')).quantize(Decimal('0.01'))

    # --- FIX: NEW PROPERTY TO TRACK APPLIED CREDITS ---
    @property
    def amount_credited(self):
        """Calculates the total amount of credits applied to this PO."""
        return (self.credit_applications.aggregate(total=Coalesce(Sum('amount_applied'), Decimal('0.00')))['total'] or Decimal('0.00')).quantize(Decimal('0.01'))
    # --- END OF FIX ---

    @property
    def total_discount(self):
        total_discount_amount = StockItem.objects.filter(
            purchase_order_item__purchase_order=self
        ).aggregate(
            total=Coalesce(Sum(F('quantity') * F('base_cost_price') * F('discount_percentage') / 100), Decimal('0.00'))
        )['total']
        return total_discount_amount.quantize(Decimal('0.01'))

    # --- FIX: UPDATE BALANCE DUE CALCULATION ---
    @property
    def balance_due(self):
        """Calculates what is owed to the supplier after payments and applied credits."""
        return (self.grand_total - self.amount_paid - self.amount_credited).quantize(Decimal('0.01'))
    # --- END OF FIX ---

    @property
    def has_pending_returns(self):
        """Checks if there are any returns for this PO that are not yet fully processed."""
        return self.returns.filter(
            status__in=['PENDING', 'PARTIALLY_PROCESSED']
        ).exists()

    def update_status(self):
        if not self.items.exists():
            self.status = 'PENDING'
        else:
            total_ord = self.items.aggregate(total=Coalesce(Sum('quantity'), Value(0)))['total']
            total_rec = self.items.aggregate(total=Coalesce(Sum('quantity_received'), Value(0)))['total']
            if total_rec == 0:
                self.status = 'PENDING'
            elif total_rec < total_ord:
                self.status = 'PARTIALLY_RECEIVED'
            else:
                self.status = 'COMPLETED'
        super().save(update_fields=['status'])


# ========== SupplierPayment ==========

class SupplierPayment(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='payments')
    payment_date = models.DateField(default=timezone.now)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    PAYMENT_METHODS = [
        ('CASH', 'Cash'), ('UPI', 'UPI'), ('BANK', 'Bank Transfer'),
        ('CHEQUE', 'Cheque'), ('CREDIT_CARD', 'Credit Card'),
        ('AMAZON_PAY', 'Amazon Pay Balance'), ('OTHER', 'Other'),
    ]
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='BANK')
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-payment_date']

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.purchase_order.update_status()

# ========== PurchaseReturn ==========

class PurchaseReturn(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Action'),
        ('REFUNDED', 'Refunded'),
        ('REPLACED', 'Replaced'),
        ('PARTIALLY_PROCESSED', 'Partially Processed'),
        ('FULLY_PROCESSED', 'Fully Processed'),
    ]
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='returns'
    )
    stock_item = models.ForeignKey(StockItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    reason = models.TextField(blank=True)
    return_date = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default='PENDING')

    class Meta:
        ordering = ['-return_date']

    def __str__(self):
        po_str = f"for PO #{self.purchase_order.pk}" if self.purchase_order else "(General Return)"
        return f"Return of {self.quantity} x {self.stock_item.product_variant} {po_str}"

    @property
    def total_value(self):
        if self.stock_item and self.stock_item.cost_price is not None:
            return (self.quantity * self.stock_item.cost_price).quantize(Decimal('0.01'))
        return Decimal('0.00')

    @property
    def quantity_replaced(self):
        return self.replacementitem_set.aggregate(total=Coalesce(Sum('quantity'), 0))['total']

    @property
    def amount_refunded(self):
        return self.supplierrefund_set.aggregate(total=Coalesce(Sum('amount'), Decimal('0.00')))['total']

    @property
    def value_of_items_replaced(self):
        if self.stock_item and self.stock_item.cost_price is not None:
            return (self.quantity_replaced * self.stock_item.cost_price).quantize(Decimal('0.01'))
        return Decimal('0.00')

    @property
    def value_pending_action(self):
        """Calculates the financial value of items not yet actioned."""
        pending_value = self.total_value - self.value_of_items_replaced - self.amount_refunded
        return max(pending_value, Decimal('0.00'))

    # --- FIX: RECALCULATE QUANTITY PENDING BASED ON VALUE ---
    @property
    def quantity_pending_action(self):
        """Calculates the equivalent number of items pending action based on the remaining value."""
        cost_price = self.stock_item.cost_price
        if cost_price is None or cost_price <= 0:
            # Fallback for safety, though cost_price should always exist for a returned item
            return self.quantity - self.quantity_replaced
        
        # Use floor division to get a whole number of items
        return int(self.value_pending_action / cost_price)
    # --- END OF FIX ---

    def update_status(self):
        # The 0.01 threshold handles potential floating point inaccuracies
        if self.value_pending_action < Decimal('0.01'):
            self.status = 'FULLY_PROCESSED'
        elif self.quantity_replaced > 0 or self.amount_refunded > 0:
            self.status = 'PARTIALLY_PROCESSED'
        else:
            self.status = 'PENDING'
        self.save(update_fields=['status'])

    def clean(self):
        pass

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

class SupplierCredit(models.Model):
    """Represents a credit a supplier owes to the clinic."""
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='credits')
    source_refund = models.OneToOneField('SupplierRefund', on_delete=models.CASCADE, related_name='credit_note')
    initial_amount = models.DecimalField(max_digits=10, decimal_places=2)
    balance = models.DecimalField(max_digits=10, decimal_places=2)
    date_issued = models.DateField(default=timezone.now)
    notes = models.TextField(blank=True)
    is_fully_used = models.BooleanField(default=False)

    class Meta:
        ordering = ['-date_issued']

    def __str__(self):
        return f"Credit of {self.initial_amount} for {self.supplier.name} (Balance: {self.balance})"

class CreditApplication(models.Model):
    """Represents the application of a credit to a specific Purchase Order."""
    credit = models.ForeignKey(SupplierCredit, on_delete=models.CASCADE, related_name='applications')
    applied_to_po = models.ForeignKey('PurchaseOrder', on_delete=models.CASCADE, related_name='credit_applications')
    amount_applied = models.DecimalField(max_digits=10, decimal_places=2)
    date_applied = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.amount_applied} of credit {self.credit.pk} applied to PO #{self.applied_to_po.pk}"

# ========== ReplacementItem ==========
class ReplacementItem(models.Model):
    purchase_return = models.ForeignKey(PurchaseReturn, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    created_stock_item = models.OneToOneField(
        StockItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='source_replacement_item'
    )
    batch_number = models.CharField(max_length=100, help_text="Batch number of the new replacement stock.")
    expiry_date = models.DateField(null=True, blank=True, help_text="Expiry date of the new replacement stock.")
    date_received = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.quantity} units replaced for return #{self.purchase_return.pk}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        
        if is_new:
            original_stock = self.purchase_return.stock_item
            
            new_stock_item = StockItem.objects.create(
                product_variant=original_stock.product_variant,
                supplier=original_stock.supplier,
                purchase_order_item=None,
                batch_number=self.batch_number,
                expiry_date=self.expiry_date,
                quantity=self.quantity,
                mrp=original_stock.mrp,
                base_cost_price=original_stock.base_cost_price,
                discount_percentage=original_stock.discount_percentage,
                gst_percentage=original_stock.gst_percentage,
                cost_price=original_stock.cost_price,
                source='REPLACEMENT'
            )
            self.created_stock_item = new_stock_item

        super().save(*args, **kwargs)

        if self.purchase_return:
            self.purchase_return.update_status()


class SupplierRefund(models.Model):
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='refunds'
    )
    purchase_return = models.ForeignKey(
        PurchaseReturn,
        on_delete=models.CASCADE,
        related_name='supplierrefund_set',
        null=True, 
        blank=True
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    refund_date = models.DateField(default=timezone.now)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-refund_date']

    def __str__(self):
        po_str = f"for PO #{self.purchase_order.pk}" if self.purchase_order else "(General)"
        return f"Refund {self.amount} {po_str}"

    def save(self, *args, **kwargs):
        with transaction.atomic():
            super().save(*args, **kwargs)
            if self.purchase_return:
                self.purchase_return.update_status()
            if self.purchase_order:
                self.purchase_order.update_status()