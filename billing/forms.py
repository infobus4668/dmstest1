# billing/forms.py

from django import forms
from django.forms import inlineformset_factory, formset_factory
from django.db import models
from .models import (
    Supplier, Product, ProductVariant, StockItem, StockAdjustment,
    Service, Invoice, InvoiceItem, InvoicePayment, Refund,
    PurchaseOrder, PurchaseOrderItem, SupplierPayment, PurchaseReturn, SupplierRefund,
    StockItemTransaction, ReplacementItem
)
from phonenumber_field.phonenumber import to_python, PhoneNumber
from phonenumbers.data import _COUNTRY_CODE_TO_REGION_CODE
from babel import Locale
import re
from staff.models import StaffMember
from patients.models import Patient
from django.core.exceptions import ValidationError
from decimal import Decimal
from django.db.models import Sum, F, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce
from django_select2 import forms as s2forms
from django.utils import timezone


# ================== Country Code Choices ==================
def get_country_choices():
    english_locale = Locale.parse("en")
    choices = [('', '---------')]
    processed_codes = set()
    for code, region_codes in sorted(_COUNTRY_CODE_TO_REGION_CODE.items()):
        primary_region = region_codes[0]
        if primary_region in processed_codes:
            continue
        try:
            country_name = english_locale.territories.get(primary_region, primary_region)
            choices.append((str(code), f"{country_name} (+{code})"))
        except Exception:
            choices.append((str(code), f"{primary_region} (+{code})"))
        processed_codes.add(primary_region)
    return sorted(choices, key=lambda x: x[1])

# ================== Supplier Form ==================
class SupplierForm(forms.ModelForm):
    country_code = forms.ChoiceField(
        label="Country Code",
        choices=get_country_choices,
        initial='91',
        required=True
    )
    national_number = forms.CharField(
        label="Phone Number",
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'e.g., 9876543210'})
    )

    class Meta:
        model = Supplier
        fields = ['name', 'category', 'contact_person', 'country_code', 'national_number', 'email', 'address']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.phone_number:
            if isinstance(self.instance.phone_number, PhoneNumber):
                self.fields['country_code'].initial = str(self.instance.phone_number.country_code)
                self.fields['national_number'].initial = str(self.instance.phone_number.national_number)
            else:
                phone = str(self.instance.phone_number)
                if phone.startswith('+') and len(phone) > 3:
                    for code, _ in get_country_choices():
                        if code and phone.startswith('+' + code):
                            self.fields['country_code'].initial = code
                            self.fields['national_number'].initial = phone[len(code)+1:]
                            break
        for field_name, field in self.fields.items():
            if 'class' not in field.widget.attrs:
                field.widget.attrs.update({'class': 'form-control'})
            if field_name == 'country_code':
                field.widget.attrs.update({'class': 'form-select'})

    def clean(self):
        cleaned_data = super().clean()
        country_code = cleaned_data.get("country_code")
        national_number = cleaned_data.get("national_number")
        phone_number = None

        if country_code and national_number:
            try:
                phone_number = to_python(f"+{country_code}{national_number}")
                if not (phone_number and phone_number.is_valid()):
                    self.add_error('national_number', "The phone number is not valid for the selected country.")
            except Exception:
                self.add_error('national_number', "Invalid phone number format.")

            if not self.errors.get('national_number'):
                supplier_qs = Supplier.objects.filter(phone_number=phone_number).exclude(pk=self.instance.pk)
                if supplier_qs.exists():
                    self.add_error('national_number', f"This phone number is already in use by supplier: {supplier_qs.first().name}.")

                from staff.models import StaffMember
                staff = StaffMember.objects.filter(contact_number=phone_number).first()
                if staff:
                    self.add_error('national_number', f"This phone number is already in use by staff: {staff.name}.")

                from patients.models import Patient
                patient = Patient.objects.filter(contact_number=phone_number).first()
                if patient:
                    self.add_error('national_number', f"This phone number is already in use by patient: {patient.name}.")

                from lab_cases.models import DentalLab
                dental_lab = DentalLab.objects.filter(contact_number=phone_number).first()
                if dental_lab:
                    self.add_error('national_number', f"This phone number is already in use by dental lab: {dental_lab.name}.")

                cleaned_data['phone_number'] = phone_number
        elif country_code or national_number:
            self.add_error('national_number', "Both country code and phone number are required.")
        else:
            cleaned_data['phone_number'] = None

        email = cleaned_data.get("email")
        if email:
            from staff.models import StaffMember
            staff = StaffMember.objects.filter(user__email__iexact=email).first()
            if staff:
                name = f"{staff.user.first_name} {staff.user.last_name}".strip() or staff.user.username
                self.add_error('email', f"This email address is already in use by staff: {name}.")

            supplier = Supplier.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).first()
            if supplier:
                self.add_error('email', f"This email address is already in use by supplier: {supplier.name}.")

            from lab_cases.models import DentalLab
            dental_lab = DentalLab.objects.filter(email__iexact=email).first()
            if dental_lab:
                self.add_error('email', f"This email address is already in use by dental lab: {dental_lab.name}.")

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number:
            instance.phone_number = phone_number
        if commit:
            instance.save()
        return instance

# ========== Additional Model Forms with Select2 Enhancements ==========

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'category', 'description', 'is_stockable', 'requires_expiry_tracking', 'is_active']

class ProductVariantForm(forms.ModelForm):
    class Meta:
        model = ProductVariant
        fields = ['product', 'variant_description', 'brand', 'sku', 'price', 'low_stock_threshold', 'is_active']
        widgets = {
            'product': s2forms.Select2Widget
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].empty_label = "Select a Product..."


class StockItemForm(forms.ModelForm):
    batch_number = forms.CharField(
        required=True,
        max_length=100,
        label="Batch Number",
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text="Batch number is required."
    )

    class Meta:
        model = StockItem
        fields = [
            'product_variant', 'supplier', 'purchase_order_item',
            'batch_number', 'expiry_date', 'quantity', 'mrp',
            'base_cost_price', 'discount_percentage', 'gst_percentage',
            'cost_price', 'date_received'
        ]
        widgets = {
            'product_variant': s2forms.Select2Widget,
            'supplier': s2forms.Select2Widget,
            'purchase_order_item': s2forms.Select2Widget,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product_variant'].empty_label = "Select a Variant..."
        self.fields['supplier'].empty_label = "Select a Supplier..."
        self.fields['purchase_order_item'].empty_label = "Select a PO..."


    def clean_batch_number(self):
        value = self.cleaned_data.get('batch_number')
        if not value or not value.strip():
            raise forms.ValidationError("Batch number is required for all received products.")
        return value

class StockAdjustmentForm(forms.ModelForm):
    class Meta:
        model = StockAdjustment
        fields = ['product_variant', 'adjustment_type', 'quantity', 'reason', 'notes', 'adjustment_date']
        widgets = {
            'product_variant': s2forms.Select2Widget
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product_variant'].empty_label = "Select a Product Variant..."


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ['name', 'description', 'price', 'is_active']

# ================== INVOICING (FIXED) ==================

class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ['patient', 'doctor', 'appointment', 'invoice_date', 'due_date', 'discount', 'notes']
        widgets = {
            'patient': forms.Select(attrs={'class': 'invoice-header-select'}),
            'doctor': forms.Select(attrs={'class': 'invoice-header-select'}),
            'appointment': forms.Select(attrs={'class': 'invoice-header-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['patient'].empty_label = "Select a Patient..."
        self.fields['doctor'].empty_label = "Select a Doctor..."
        self.fields['appointment'].empty_label = "Select an Appointment..."

class InvoiceItemForm(forms.ModelForm):
    product_variant = forms.ModelChoiceField(
        queryset=ProductVariant.objects.annotate(
            total_quantity=Coalesce(Sum('stock_items__quantity'), 0),
            total_sold=Coalesce(Sum('stock_items__transactions__quantity'), 0),
            total_returned=Coalesce(Sum('stock_items__purchasereturn__quantity'), 0)
        ).annotate(
            stock_available=F('total_quantity') - F('total_sold') - F('total_returned')
        ).filter(is_active=True, stock_available__gt=0),
        widget=forms.Select(attrs={'class': 'invoice-item-select'}),
        required=False,
        label="Product"
    )

    class Meta:
        model = InvoiceItem
        fields = ['service', 'product_variant', 'stock_item', 'description', 'quantity', 'unit_price', 'discount']
        widgets = {
            'service': forms.Select(attrs={'class': 'invoice-item-select'}),
            'stock_item': forms.Select(attrs={'class': 'invoice-item-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['service'].queryset = Service.objects.filter(is_active=True)
        self.fields['service'].empty_label = "Select a Service..."
        self.fields['product_variant'].empty_label = "Select a Product..."
        self.fields['stock_item'].empty_label = "Select Batch..."

        # Default to an empty queryset
        self.fields['stock_item'].queryset = StockItem.objects.none()

        # If form is bound to data (POST request), dynamically set the queryset for validation
        if self.data:
            try:
                # Find the product_variant id from the submitted data
                variant_id = int(self.data.get(self.prefix + '-product_variant'))
                # Set the queryset to all stock items for that variant
                self.fields['stock_item'].queryset = StockItem.objects.filter(product_variant_id=variant_id).order_by('expiry_date')
            except (ValueError, TypeError):
                # Handle cases where the data is missing or not a number
                pass
        # If form is for an existing instance (editing), set the queryset and initial values
        elif self.instance.pk and self.instance.stock_item:
            self.fields['stock_item'].queryset = StockItem.objects.filter(product_variant=self.instance.stock_item.product_variant).order_by('expiry_date')
            self.initial['product_variant'] = self.instance.stock_item.product_variant

# Inline Formset for Invoice Items
InvoiceItemFormSet = inlineformset_factory(
    Invoice,
    InvoiceItem,
    form=InvoiceItemForm,
    fields=['service', 'product_variant', 'stock_item', 'description', 'quantity', 'unit_price', 'discount'],
    extra=1,
    can_delete=True
)

class InvoicePaymentForm(forms.ModelForm):
    class Meta:
        model = InvoicePayment
        fields = ['payment_date', 'amount', 'payment_method', 'notes']

    def __init__(self, *args, **kwargs):
        self.invoice = kwargs.pop('invoice', None)
        super().__init__(*args, **kwargs)
        if self.invoice and not self.initial.get('amount'):
             self.fields['amount'].initial = self.invoice.balance_due

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        
        if amount is not None and amount <= Decimal('0.00'):
            raise ValidationError('Amount must be greater than zero.')
            
        if not self.invoice:
            return amount

        balance_due = self.invoice.balance_due
        
        if amount is not None and amount > balance_due:
            raise ValidationError(f'Payment of {amount} exceeds the outstanding balance of {balance_due:.2f}.')
            
        return amount

class RefundForm(forms.ModelForm):
    class Meta:
        model = Refund
        fields = ['refund_date', 'amount', 'method', 'notes']

    def __init__(self, *args, **kwargs):
        self.invoice = kwargs.pop('invoice', None)
        super().__init__(*args, **kwargs)

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')

        if amount is not None and amount <= Decimal('0.00'):
            raise ValidationError('Refund amount must be greater than zero.')

        if not self.invoice:
            return amount

        if self.invoice.balance_due >= 0:
             raise ValidationError("A refund can only be recorded for an overpaid invoice.")

        max_refundable = -self.invoice.balance_due

        if amount is not None and amount > max_refundable:
            raise ValidationError(f'Refund of {amount} exceeds the maximum refundable amount of {max_refundable:.2f}.')

        return amount

class PurchaseOrderForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = ['supplier', 'order_date', 'notes']
        widgets = {
            'supplier': s2forms.Select2Widget
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['supplier'].empty_label = "Select a Supplier..."


class PurchaseOrderItemForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrderItem
        fields = ['product_variant', 'quantity', 'cost_price']
        widgets = {
            'product_variant': s2forms.Select2Widget
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cost_price'].required = False
        self.fields['product_variant'].empty_label = "Select a Product Variant..."


PurchaseOrderItemFormSet = inlineformset_factory(
    PurchaseOrder, PurchaseOrderItem, form=PurchaseOrderItemForm,
    fields=['product_variant', 'quantity', 'cost_price'], extra=0, can_delete=True
)

class SupplierPaymentForm(forms.ModelForm):
    class Meta:
        model = SupplierPayment
        fields = ['payment_date', 'amount', 'payment_method', 'notes']
        widgets = {
            'payment_method': s2forms.Select2Widget
        }

    def __init__(self, *args, **kwargs):
        self.purchase_order = kwargs.pop('purchase_order', None)
        super().__init__(*args, **kwargs)
        if 'payment_method' in self.fields:
            self.fields['payment_method'].empty_label = "Select a Payment Method..."


    def clean_amount(self):
        amount = self.cleaned_data.get('amount')

        if amount is not None and amount <= Decimal('0.00'):
            raise ValidationError('Payment amount must be greater than zero.')

        if not self.purchase_order:
            return amount

        balance_due = self.purchase_order.balance_due

        if amount is not None and amount > balance_due:
            raise ValidationError(f'Payment of {amount} exceeds the outstanding balance of {balance_due:.2f}.')

        return amount

class PurchaseOrderFilterForm(forms.Form):
    supplier = forms.ModelChoiceField(
        queryset=Supplier.objects.all(),
        required=False,
        widget=s2forms.Select2Widget
    )
    status = forms.ChoiceField(
        choices=[('', 'All')] + PurchaseOrder.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['supplier'].empty_label = "All Suppliers"


class ReceiveStockForm(forms.Form):
    purchase_order_item_id = forms.IntegerField(widget=forms.HiddenInput)
    quantity_to_receive = forms.IntegerField(min_value=1, required=False, label="Qty Rcvd.")
    mrp = forms.DecimalField(max_digits=10, decimal_places=2, required=False)
    base_cost_price = forms.DecimalField(max_digits=10, decimal_places=2, required=False, label="Base Cost")
    discount_percentage = forms.DecimalField(label="Disc. (%)", max_digits=5, decimal_places=2, required=False)
    discount_amount = forms.DecimalField(label="Disc. (₹)", max_digits=10, decimal_places=2, required=False)
    gst_percentage = forms.DecimalField(max_digits=5, decimal_places=2, required=False, label="GST (%)")
    cost_price = forms.DecimalField(max_digits=10, decimal_places=2, required=False, label="Final Cost")
    batch_number = forms.CharField(max_length=100, required=False, label="Batch No.")
    expiry_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    date_received = forms.DateTimeField(required=False, widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}))

    def __init__(self, *args, **kwargs):
        self.purchase_order_item = kwargs.pop('purchase_order_item', None)
        super().__init__(*args, **kwargs)

    def clean_expiry_date(self):
        expiry_date = self.cleaned_data.get('expiry_date')
        if expiry_date and expiry_date < timezone.now().date():
            raise ValidationError("Expiry date cannot be in the past.")
        return expiry_date

    def clean_date_received(self):
        date_received = self.cleaned_data.get('date_received')
        
        if not date_received:
            return None

        if date_received > timezone.now():
            raise ValidationError("Date of receipt cannot be in the future.")

        if self.purchase_order_item:
            if date_received < self.purchase_order_item.purchase_order.order_date:
                raise ValidationError(f"Date of receipt cannot be earlier than the order date ({self.purchase_order_item.purchase_order.order_date.strftime('%d-%m-%Y')}).")
        
        return date_received

    def clean(self):
        cleaned_data = super().clean()
        qty = cleaned_data.get('quantity_to_receive')
        
        if not qty or qty <= 0:
            return cleaned_data

        base_cost = cleaned_data.get('base_cost_price')
        batch_number = cleaned_data.get('batch_number')
        mrp = cleaned_data.get('mrp')
        
        expiry_date = cleaned_data.get('expiry_date')
        if self.purchase_order_item and self.purchase_order_item.product_variant.product.requires_expiry_tracking:
            if not expiry_date:
                self.add_error('expiry_date', 'Expiry date is required for this product.')

        if mrp is None and self.purchase_order_item:
            mrp = self.purchase_order_item.product_variant.price

        if not base_cost:
            self.add_error('base_cost_price', 'Base Cost is required.')
        if not batch_number:
            self.add_error('batch_number', 'Batch No is required.')

        if base_cost and mrp and base_cost > mrp:
            self.add_error('base_cost_price', f'Base Cost (₹{base_cost}) cannot be higher than MRP (₹{mrp}).')

        discount_perc = cleaned_data.get('discount_percentage')
        discount_amt = cleaned_data.get('discount_amount')

        if discount_perc and discount_amt:
            if discount_perc > 0 and discount_amt > 0:
                 self.add_error('discount_percentage', "Provide discount as either a percentage or an amount, not both.")

        if base_cost and qty and discount_amt:
            total_base_cost = base_cost * Decimal(qty)
            if discount_amt > total_base_cost:
                self.add_error('discount_amount', f'Discount (₹{discount_amt}) cannot be greater than the total base cost (₹{total_base_cost}).')

        if base_cost:
            final_discount_percentage = Decimal('0.00')
            if discount_perc is not None:
                final_discount_percentage = discount_perc
            elif discount_amt is not None and qty > 0:
                per_unit_discount = discount_amt / Decimal(qty)
                if base_cost > 0:
                    final_discount_percentage = (per_unit_discount / base_cost) * Decimal('100')
            
            cost_after_discount = base_cost * (Decimal('1') - final_discount_percentage / Decimal('100'))
            gst_perc = cleaned_data.get('gst_percentage') or Decimal('0.00')
            final_cost = cost_after_discount * (Decimal('1') + gst_perc / Decimal('100'))

            if mrp and final_cost > mrp:
                error_message = (
                    f"Final Cost (₹{final_cost:.2f}) exceeds MRP (₹{mrp}). "
                    f"Suggestion: Reduce the Base Cost or increase the MRP."
                )
                self.add_error(None, error_message)

        if qty and self.purchase_order_item:
            if qty > self.purchase_order_item.quantity_remaining:
                self.add_error('quantity_to_receive', f"Cannot receive more than the remaining {self.purchase_order_item.quantity_remaining} items.")

        return cleaned_data

class BaseReceiveStockFormSet(forms.BaseFormSet):
    def get_form_kwargs(self, index):
        kwargs = super().get_form_kwargs(index)
        items_to_receive = kwargs.get('items_to_receive', [])
        
        if index is not None and index < len(items_to_receive):
            kwargs['purchase_order_item'] = items_to_receive[index]
        
        if 'items_to_receive' in kwargs:
            del kwargs['items_to_receive']
            
        return kwargs

ReceiveStockFormSet = formset_factory(ReceiveStockForm, formset=BaseReceiveStockFormSet, extra=0)

class UnifiedReturnForm(forms.ModelForm):
    class Meta:
        model = PurchaseReturn
        fields = ['quantity', 'reason']
        widgets = {
            'reason': forms.Select(choices=[
                ('', '---------'),
                ('Damaged', 'Damaged'),
                ('Expired', 'Expired'),
                ('Wrong Item Supplied', 'Wrong Item Supplied'),
                ('Quality Issue', 'Quality Issue'),
                ('Other', 'Other'),
            ])
        }

    def __init__(self, *args, **kwargs):
        self.stock_item = kwargs.pop('stock_item', None)
        super().__init__(*args, **kwargs)

    def clean_quantity(self):
        quantity = self.cleaned_data.get('quantity')
        if self.stock_item and quantity:
            if quantity > self.stock_item.quantity_available:
                raise ValidationError(f"Cannot return more than the available quantity ({self.stock_item.quantity_available}).")
        return quantity


class ReplacementStockForm(forms.Form):
    quantity = forms.IntegerField(min_value=1, label="Quantity Replaced")
    batch_number = forms.CharField(max_length=100, required=True, label="New Batch Number")
    expiry_date = forms.DateField(required=False, label="New Expiry Date", widget=forms.DateInput(attrs={'type': 'date'}))
    notes = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False)

    def __init__(self, *args, **kwargs):
        self.purchase_return = kwargs.pop('purchase_return', None)
        super().__init__(*args, **kwargs)
        if self.purchase_return:
            self.fields['quantity'].initial = self.purchase_return.quantity_pending_action
            self.fields['quantity'].help_text = f"Max: {self.purchase_return.quantity_pending_action}"

    def clean_quantity(self):
        quantity = self.cleaned_data.get('quantity')
        if self.purchase_return and quantity > self.purchase_return.quantity_pending_action:
            raise ValidationError(
                f"Quantity ({quantity}) cannot exceed the amount pending action ({self.purchase_return.quantity_pending_action})."
            )
        return quantity

    def clean_expiry_date(self):
        expiry_date = self.cleaned_data.get('expiry_date')
        if expiry_date and expiry_date < timezone.now().date():
            raise ValidationError("Expiry date cannot be in the past.")
        return expiry_date

    def clean(self):
        cleaned_data = super().clean()
        expiry_date = cleaned_data.get('expiry_date')
        
        if self.purchase_return:
            product = self.purchase_return.stock_item.product_variant.product
            if product.requires_expiry_tracking and not expiry_date:
                self.add_error('expiry_date', 'Expiry date is required for this product.')
                
        return cleaned_data

class SupplierRefundForm(forms.ModelForm):
    class Meta:
        model = SupplierRefund
        fields = ['refund_date', 'amount', 'notes']

    def __init__(self, *args, **kwargs):
        self.purchase_return = kwargs.pop('purchase_return', None)
        super().__init__(*args, **kwargs)

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is None:
            raise ValidationError('Amount is required.')
        
        if amount <= Decimal('0.00'):
            raise ValidationError('Refund amount must be greater than zero.')

        if self.purchase_return:
            max_refundable = self.purchase_return.value_pending_action
            if amount > max_refundable:
                raise ValidationError(f'Refund of {amount} exceeds the maximum refundable amount of {max_refundable:.2f} for the items pending action.')
        
        return amount

class GeneralSupplierRefundForm(forms.ModelForm):
    class Meta:
        model = SupplierRefund
        fields = ['refund_date', 'amount', 'notes']

    def __init__(self, *args, **kwargs):
        self.purchase_return = kwargs.pop('purchase_return', None)
        super().__init__(*args, **kwargs)

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is None:
            raise ValidationError('Amount is required.')
        
        if amount <= Decimal('0.00'):
            raise ValidationError('Refund amount must be greater than zero.')

        if self.purchase_return:
            max_refundable = self.purchase_return.value_pending_action
            if amount > max_refundable:
                raise ValidationError(f'Refund of {amount} exceeds the maximum refundable amount of {max_refundable:.2f} for the items pending action.')
        
        return amount