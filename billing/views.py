# billing/views.py

import json
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from django.db.models import F, Q, Sum, Prefetch, OuterRef, Subquery, IntegerField
from django.db.models.functions import Coalesce
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.utils import timezone
from django.urls import reverse_lazy, reverse

from .models import (
    Service, Product, ProductVariant, Invoice, InvoiceItem, StockItem, Supplier,
    PurchaseOrder, PurchaseOrderItem, SupplierPayment, StockAdjustment, InvoicePayment,
Refund, PurchaseReturn, SupplierRefund, ReplacementItem, SupplierCredit, CreditApplication
)
from .forms import (
    ServiceForm, ProductForm, ProductVariantForm,
    SupplierForm, PurchaseOrderForm, PurchaseOrderItemFormSet,
    StockAdjustmentForm,
    InvoiceForm, InvoiceItemFormSet, InvoicePaymentForm,
    RefundForm, PurchaseOrderFilterForm, SupplierPaymentForm,
    ReceiveStockForm, ReceiveStockFormSet, StockItemForm,
    UnifiedReturnForm, GeneralSupplierRefundForm, ReplacementStockForm,
    SupplierRefundForm
)
from patients.models import Patient
from staff.models import StaffMember
from appointments.models import Appointment

# ================= HELPER FUNCTIONS ====================

def get_invoice_context_data(invoice_instance=None):
    services = {s.pk: {'name': s.name, 'price': str(s.price)} for s in Service.objects.filter(is_active=True)}
    
    product_variants = ProductVariant.objects.filter(is_active=True)
    products_data = {v.pk: {'name': str(v)} for v in product_variants}

    available_stock = StockItem.objects.annotate(
        sold_qty=Coalesce(Sum('transactions__quantity'), 0),
        returned_qty=Coalesce(Sum('purchasereturn__quantity'), 0)
    ).filter(
        quantity__gt=F('sold_qty') + F('returned_qty'),
        product_variant__in=product_variants
    ).order_by('expiry_date')

    batches_data = {}
    for stock in available_stock:
        variant_id = stock.product_variant.id
        if variant_id not in batches_data:
            batches_data[variant_id] = []
        
        batches_data[variant_id].append({
            'pk': stock.pk,
            'name': str(stock),
            'mrp': str(stock.mrp),
            'available': stock.quantity_available,
        })

    return json.dumps({
        'services': services,
        'products': products_data,
        'batches': batches_data,
    })

# =============== PRODUCT & VARIANT MANAGEMENT ===============

class ProductListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Product
    template_name = 'billing/product_list.html'
    context_object_name = 'products'
    permission_required = 'billing.view_product'
    paginate_by = 20

class ProductDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Product
    template_name = 'billing/product_detail.html'
    context_object_name = 'product'
    permission_required = 'billing.view_product'
    def get_queryset(self):
        return Product.objects.prefetch_related('variants')

class ProductCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = 'billing/product_form.html'
    permission_required = 'billing.add_product'
    def get_success_url(self):
        messages.success(self.request, f"Product '{self.object.name}' created successfully. You can now add variants.")
        return reverse('billing:product_detail', kwargs={'pk': self.object.pk})
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Create New Generic Product'
        return context

class ProductUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = 'billing/product_form.html'
    permission_required = 'billing.change_product'
    def get_success_url(self):
        messages.success(self.request, 'Product updated successfully.')
        return reverse('billing:product_detail', kwargs={'pk': self.object.pk})
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"Edit Product: {self.object.name}"
        return context

class ProductDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Product
    template_name = 'billing/product_confirm_delete.html'
    success_url = reverse_lazy('billing:product_list')
    permission_required = 'billing.delete_product'
    def form_valid(self, form):
        messages.success(self.request, f"Product '{self.object.name}' and all its variants have been deleted.")
        return super().form_valid(form)

@login_required
@permission_required('billing.add_productvariant', raise_exception=True)
def variant_create_view(request, product_pk):
    product = get_object_or_404(Product, pk=product_pk)
    if request.method == 'POST':
        form = ProductVariantForm(request.POST)
        if form.is_valid():
            variant = form.save(commit=False)
            variant.product = product
            variant.save()
            messages.success(request, f'New variant "{variant}" created successfully.')
            return redirect('billing:product_detail', pk=product.pk)
    else:
        form = ProductVariantForm(initial={'product': product})
    return render(request, 'billing/variant_form.html', {'form': form, 'product': product, 'page_title': f'Add Variant to {product.name}'})

@login_required
@permission_required('billing.change_productvariant', raise_exception=True)
def variant_edit_view(request, pk):
    variant = get_object_or_404(ProductVariant.objects.select_related('product'), pk=pk)
    if request.method == 'POST':
        form = ProductVariantForm(request.POST, instance=variant)
        if form.is_valid():
            form.save()
            messages.success(request, 'Variant updated successfully.')
            return redirect('billing:product_detail', pk=variant.product.pk)
    else:
        form = ProductVariantForm(instance=variant)
    return render(request, 'billing/variant_form.html', {'form': form, 'product': variant.product, 'page_title': f'Edit Variant: {variant}'})

@login_required
@permission_required('billing.delete_productvariant', raise_exception=True)
def variant_delete_view(request, pk):
    variant = get_object_or_404(ProductVariant, pk=pk)
    product_pk = variant.product.pk
    if request.method == 'POST':
        variant_name = str(variant)
        variant.delete()
        messages.success(request, f'Variant "{variant_name}" has been deleted.')
        return redirect('billing:product_detail', pk=product_pk)
    return render(request, 'billing/variant_confirm_delete.html', {'variant': variant})

# =============== PURCHASE ORDER & STOCK RECEIPT VIEWS ===============

@login_required
@permission_required('billing.add_purchaseorder', raise_exception=True)
def create_purchase_order_view(request, pk=None):
    initial_items = []
    if pk:
        try:
            variant = ProductVariant.objects.get(pk=pk)
            initial_items.append({'product_variant': variant, 'quantity': 1})
        except ProductVariant.DoesNotExist:
            messages.error(request, "The selected product variant does not exist.")
            return redirect('billing:inventory_list')
    if request.method == 'POST':
        form = PurchaseOrderForm(request.POST)
        formset = PurchaseOrderItemFormSet(request.POST, prefix='items')
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                purchase_order = form.save()
                formset.instance = purchase_order
                formset.save()
            messages.success(request, 'Purchase Order created successfully.')
            return redirect('billing:purchase_order_detail', pk=purchase_order.pk)
    else:
        form = PurchaseOrderForm()
        formset = PurchaseOrderItemFormSet(initial=initial_items if initial_items else [], queryset=PurchaseOrderItem.objects.none(), prefix='items')
    context = {
        'form': form,
        'formset': formset,
        'page_title': 'Create New Purchase Order'
    }
    return render(request, 'billing/purchase_order_form.html', context)


@login_required
@permission_required('billing.change_purchaseorder', raise_exception=True)
def edit_purchase_order_view(request, pk):
    po = get_object_or_404(PurchaseOrder, pk=pk)
    if po.status != 'PENDING':
        messages.error(request, f"This purchase order cannot be edited as its status is '{po.get_status_display()}'.")
        return redirect('billing:purchase_order_detail', pk=po.pk)
    if request.method == 'POST':
        form = PurchaseOrderForm(request.POST, instance=po)
        formset = PurchaseOrderItemFormSet(request.POST, instance=po, prefix='items')
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                form.save()
                formset.save()
            messages.success(request, 'Purchase Order updated successfully.')
            return redirect('billing:purchase_order_detail', pk=po.pk)
    else:
        form = PurchaseOrderForm(instance=po)
        formset = PurchaseOrderItemFormSet(instance=po, prefix='items')
    context = {
        'form': form,
        'formset': formset,
        'po': po,
        'page_title': f'Edit PO #{po.pk}'
    }
    return render(request, 'billing/purchase_order_form.html', context)

@login_required
@permission_required('billing.view_purchaseorder', raise_exception=True)
def purchase_order_detail_view(request, pk):
    po = get_object_or_404(PurchaseOrder.objects.prefetch_related(
        Prefetch('items', queryset=PurchaseOrderItem.objects.select_related('product_variant'))
    ), pk=pk)

    # --- REFACTOR: Use the new, more powerful helper method from the model ---
    all_returns = po._get_all_related_returns()
    
    items_with_details = []
    for item in po.items.all():
        variant_returns = [r for r in all_returns if r.stock_item.product_variant_id == item.product_variant_id]
        
        total_returned = sum(r.quantity for r in variant_returns)
        
        variant_replacements = ReplacementItem.objects.filter(purchase_return__in=variant_returns)
        total_replaced = variant_replacements.aggregate(total=Coalesce(Sum('quantity'), 0))['total']

        original_batches = StockItem.objects.filter(purchase_order_item=item)
        replacement_batches = StockItem.objects.filter(source_replacement_item__in=variant_replacements)
        
        all_batches_for_variant = list(original_batches) + list(replacement_batches)
        total_available = sum(b.quantity_available for b in all_batches_for_variant)

        items_with_details.append({
            'item': item,
            'total_returned': total_returned,
            'total_replaced': total_replaced,
            'total_available': total_available,
        })
    # --- END OF REFACTOR ---

    can_cancel_po = request.user.has_perm('billing.delete_purchaseorder') and po.status == 'PENDING'
    can_edit_po = request.user.has_perm('billing.change_purchaseorder') and po.status == 'PENDING'
    
    context = {
        'po': po,
        'items_with_details': items_with_details,
        'original_batches': StockItem.objects.filter(purchase_order_item__purchase_order=po),
        'can_cancel_po': can_cancel_po,
        'can_edit_po': can_edit_po,
    }
    return render(request, 'billing/purchase_order_detail.html', context)

@login_required
@permission_required('billing.add_stockitem', raise_exception=True)
@transaction.atomic
def receive_purchase_order_view(request, pk):
    po = get_object_or_404(PurchaseOrder.objects.select_related('supplier'), pk=pk)
    items_to_receive = list(po.items.filter(
        quantity_received__lt=F('quantity')
    ).select_related('product_variant__product').prefetch_related('received_batches'))

    if not items_to_receive:
        messages.warning(request, "This purchase order has already been fully received.")
        return redirect('billing:purchase_order_detail', pk=pk)

    form_kwargs = {'items_to_receive': items_to_receive}

    if request.method == 'POST':
        formset = ReceiveStockFormSet(request.POST, form_kwargs=form_kwargs, prefix='receive')
        if formset.is_valid():
            for form in formset.forms:
                cleaned_data = form.cleaned_data
                if not cleaned_data or not cleaned_data.get('quantity_to_receive'):
                    continue

                qty_to_receive = Decimal(cleaned_data.get('quantity_to_receive', 0))
                if qty_to_receive <= 0:
                    continue

                po_item = get_object_or_404(PurchaseOrderItem, pk=cleaned_data.get('purchase_order_item_id'))

                base_cost = cleaned_data.get('base_cost_price') or Decimal('0.00')
                discount_perc_input = cleaned_data.get('discount_percentage')
                discount_amt_input = cleaned_data.get('discount_amount')
                gst_perc = cleaned_data.get('gst_percentage') or Decimal('0.00')

                final_discount_percentage = Decimal('0.00')
                if discount_perc_input is not None:
                    final_discount_percentage = discount_perc_input
                elif discount_amt_input is not None and qty_to_receive > 0:
                    per_unit_discount_amt = discount_amt_input / qty_to_receive
                    if base_cost > 0:
                        calculated_perc = (per_unit_discount_amt / base_cost) * Decimal('100')
                        final_discount_percentage = calculated_perc.quantize(Decimal('0.01'))

                cost_after_discount = base_cost * (Decimal('1') - final_discount_percentage / Decimal('100'))
                final_cost_per_item = cost_after_discount * (Decimal('1') + gst_perc / Decimal('100'))
                final_cost_per_item = final_cost_per_item.quantize(Decimal('0.01'))

                StockItem.objects.create(
                    product_variant=po_item.product_variant,
                    supplier=po.supplier,
                    purchase_order_item=po_item,
                    quantity=qty_to_receive,
                    mrp=cleaned_data.get('mrp') or 0,
                    base_cost_price=base_cost,
                    discount_percentage=final_discount_percentage,
                    gst_percentage=gst_perc,
                    cost_price=final_cost_per_item,
                    batch_number=cleaned_data.get('batch_number'),
                    expiry_date=cleaned_data.get('expiry_date'),
                    date_received=cleaned_data.get('date_received') or timezone.now()
                )
                
                po_item.quantity_received += int(qty_to_receive)
                po_item.save(update_fields=['quantity_received'])

            po.refresh_from_db()
            po.update_status()
            messages.success(request, "Stock received and inventory updated successfully.")
            return redirect('billing:purchase_order_detail', pk=po.pk)
    else:
        initial_data = []
        for item in items_to_receive:
            local_time = timezone.localtime(timezone.now())
            initial_item_data = {
                'purchase_order_item_id': item.id,
                'quantity_to_receive': item.quantity_remaining,
                'mrp': item.product_variant.price,
                'date_received': local_time.strftime('%Y-%m-%dT%H:%M'),
            }
            initial_data.append(initial_item_data)
            
        formset = ReceiveStockFormSet(initial=initial_data, form_kwargs=form_kwargs, prefix='receive')
    
    expiry_required_map = {
        item.id: item.product_variant.product.requires_expiry_tracking
        for item in items_to_receive
    }

    forms_with_items = zip(formset.forms, items_to_receive)
    context = {
        'purchase_order': po,
        'formset': formset,
        'forms_with_items': forms_with_items,
        'page_title': f'Receive Stock for PO #{po.pk}',
        'expiry_map_json': json.dumps(expiry_required_map)
    }
    return render(request, 'billing/receive_purchase_order.html', context)

@login_required
@permission_required('billing.view_purchaseorder', raise_exception=True)
def purchase_order_list_view(request):
    # This query efficiently calculates total ordered and received quantities
    purchase_orders = PurchaseOrder.objects.annotate(
        total_ordered=Coalesce(Sum('items__quantity'), 0),
        total_received=Coalesce(Sum('items__quantity_received'), 0)
    ).annotate(
        outstanding_items=F('total_ordered') - F('total_received')
    ).select_related('supplier').prefetch_related(
        'payments', 'items__product_variant'
    ).all().order_by('-order_date')

    filter_form = PurchaseOrderFilterForm(request.GET)
    if filter_form.is_valid():
        supplier = filter_form.cleaned_data.get('supplier')
        status = filter_form.cleaned_data.get('status')
        if supplier:
            purchase_orders = purchase_orders.filter(supplier=supplier)
        if status:
            purchase_orders = purchase_orders.filter(status=status)
            
    context = {
        'purchase_orders_list': purchase_orders,
        'page_title': 'Supplier Purchase Orders',
        'filter_form': filter_form,
    }
    return render(request, 'billing/purchase_order_list.html', context)

@login_required
@permission_required('billing.delete_purchaseorder', raise_exception=True)
def cancel_purchase_order_view(request, pk):
    po = get_object_or_404(PurchaseOrder, pk=pk)
    if po.status != 'PENDING':
        messages.error(request, f"This purchase order cannot be cancelled as it is already {po.get_status_display()}.")
    elif request.method == 'POST':
        po.status = 'CANCELLED'
        po.save()
        messages.success(request, f'Purchase Order #{po.pk} has been cancelled.')
    return redirect('billing:purchase_order_detail', pk=pk)

@login_required
@permission_required('billing.add_purchasereturn', raise_exception=True)
def create_return_view(request, stock_item_pk):
    stock_item = get_object_or_404(StockItem, pk=stock_item_pk)

    if request.method == 'POST':
        form = UnifiedReturnForm(request.POST, stock_item=stock_item)
        if form.is_valid():
            purchase_return = form.save(commit=False)
            purchase_return.stock_item = stock_item
            
            if stock_item.purchase_order_item:
                purchase_return.purchase_order = stock_item.purchase_order_item.purchase_order
            else:
                purchase_return.purchase_order = None
                
            purchase_return.save()
            messages.success(request, f'Return of {purchase_return.quantity} x {stock_item.product_variant} has been recorded.')
            return redirect('billing:inventory_list')
    else:
        form = UnifiedReturnForm(stock_item=stock_item)

    context = {
        'form': form,
        'stock_item': stock_item,
        'page_title': f'Return from Batch: {stock_item.batch_number}'
    }
    return render(request, 'billing/unified_return_form.html', context)


@login_required
@permission_required('billing.view_purchasereturn', raise_exception=True)
def return_list_view(request):
    returns_list = PurchaseReturn.objects.select_related(
        'stock_item__product_variant',
        'purchase_order__supplier',
    ).prefetch_related(
        'supplierrefund_set',
        'replacementitem_set'
    ).all().order_by('-return_date')

    context = {
        'returns_list': returns_list,
        'page_title': 'All Returns & Replacements'
    }
    return render(request, 'billing/return_list.html', context)

@login_required
@permission_required('billing.add_supplierrefund', raise_exception=True)
def add_supplier_refund_view(request, po_pk, return_pk):
    purchase_order = get_object_or_404(PurchaseOrder, pk=po_pk)
    purchase_return = get_object_or_404(PurchaseReturn, pk=return_pk, purchase_order=purchase_order)

    if purchase_return.value_pending_action <= 0:
        messages.warning(request, f"This return has been fully actioned and cannot be refunded.")
        return redirect('billing:return_list')

    if request.method == 'POST':
        form = SupplierRefundForm(request.POST, purchase_return=purchase_return)
        if form.is_valid():
            with transaction.atomic():
                refund = form.save(commit=False)
                refund.purchase_order = purchase_order
                refund.purchase_return = purchase_return
                refund.save()
            messages.success(request, f"Supplier refund of ₹{refund.amount} recorded successfully.")
            return redirect('billing:return_list')
    else:
        initial_data = {
            'amount': purchase_return.value_pending_action,
            'notes': f"Refund for {purchase_return.quantity_pending_action} x {purchase_return.stock_item.product_variant} (un-replaced from total return of {purchase_return.quantity})"
        }
        form = SupplierRefundForm(purchase_return=purchase_return, initial=initial_data)

    return render(request, 'billing/add_supplier_refund.html', {
        'form': form,
        'purchase_order': purchase_order,
        'purchase_return': purchase_return,
        'page_title': f'Record Supplier Refund for PO #{purchase_order.pk}',
        'product_name': str(purchase_return.stock_item.product_variant),
        'cost_price': float(purchase_return.stock_item.cost_price)
    })

@login_required
@permission_required('billing.add_supplierrefund', raise_exception=True)
def create_general_refund_view(request, return_pk):
    purchase_return = get_object_or_404(
        PurchaseReturn.objects.select_related('stock_item'),
        pk=return_pk
    )

    if purchase_return.purchase_order:
        return redirect('billing:add_supplier_refund_for_return', po_pk=purchase_return.purchase_order.pk, return_pk=return_pk)

    if request.method == 'POST':
        form = GeneralSupplierRefundForm(request.POST, purchase_return=purchase_return)
        if form.is_valid():
            with transaction.atomic():
                refund = form.save(commit=False)
                refund.purchase_return = purchase_return
                refund.purchase_order = None
                refund.save()
            messages.success(request, f"General supplier refund of ₹{refund.amount} recorded.")
            return redirect('billing:return_list')
    else:
        initial_data = {
            'amount': purchase_return.value_pending_action,
            'notes': f"Refund for {purchase_return.quantity_pending_action} x {purchase_return.stock_item.product_variant}"
        }
        form = GeneralSupplierRefundForm(purchase_return=purchase_return, initial=initial_data)

    context = {
        'form': form,
        'purchase_return': purchase_return,
        'page_title': 'Record General Supplier Refund',
        'product_name': str(purchase_return.stock_item.product_variant),
        'cost_price': float(purchase_return.stock_item.cost_price)
    }
    return render(request, 'billing/add_general_refund.html', context)


@login_required
@permission_required('billing.add_replacementitem', raise_exception=True)
@transaction.atomic
def receive_replacement_view(request, return_pk):
    purchase_return = get_object_or_404(
        PurchaseReturn.objects.select_related(
            'stock_item__product_variant', 
            'stock_item__supplier'
        ), pk=return_pk
    )
    
    if purchase_return.quantity_pending_action <= 0:
        messages.warning(request, f"Action has already been fully completed for this return (Status: {purchase_return.get_status_display()}).")
        return redirect('billing:return_list')

    if request.method == 'POST':
        form = ReplacementStockForm(request.POST, purchase_return=purchase_return)
        if form.is_valid():
            cleaned_data = form.cleaned_data
            
            ReplacementItem.objects.create(
                purchase_return=purchase_return,
                quantity=cleaned_data['quantity'],
                batch_number=cleaned_data['batch_number'],
                expiry_date=cleaned_data.get('expiry_date'),
                notes=cleaned_data.get('notes')
            )
            
            messages.success(request, f"Replacement of {cleaned_data['quantity']} units recorded successfully.")
            return redirect('billing:return_list')
    else:
        form = ReplacementStockForm(purchase_return=purchase_return)
        
    context = {
        'form': form,
        'purchase_return': purchase_return,
        'page_title': 'Receive Replacement Stock'
    }
    return render(request, 'billing/receive_replacement_form.html', context)


# =============== INVENTORY & SUPPLIER MANAGEMENT ===============
@login_required
@permission_required('billing.view_stockitem', raise_exception=True)
def inventory_list_view(request):
    
    returned_subquery = PurchaseReturn.objects.filter(
        stock_item_id=OuterRef('pk')
    ).values('stock_item_id').annotate(total=Sum('quantity')).values('total')

    inventory = StockItem.objects.select_related(
        'product_variant__product', 'supplier'
    ).prefetch_related(
        'purchasereturn_set'
    ).annotate(
        returned_qty=Coalesce(Subquery(returned_subquery, output_field=IntegerField()), 0)
    ).order_by('-date_received')

    for item in inventory:
        latest_return = item.purchasereturn_set.order_by('-return_date').first()
        item.latest_return_status = latest_return.get_status_display() if latest_return else None
        
        if latest_return and latest_return.status in ['PENDING', 'PARTIALLY_PROCESSED']:
            item.has_active_return = True
        else:
            item.has_active_return = False

    search_query = request.GET.get('q', '')
    if search_query:
        inventory = inventory.filter(
            Q(product_variant__product__name__icontains=search_query) |
            Q(product_variant__brand__icontains=search_query) |
            Q(product_variant__sku__icontains=search_query) |
            Q(supplier__name__icontains=search_query) |
            Q(batch_number__icontains=search_query)
        )
        
    low_stock_count = 0
    all_variants = ProductVariant.objects.filter(is_active=True)
    for variant in all_variants:
        if variant.stock_quantity <= variant.low_stock_threshold:
            low_stock_count += 1

    context = {
        'inventory_list': inventory,
        'page_title': 'Inventory Stock List (All Batches)',
        'search_query': search_query,
        'low_stock_count': low_stock_count,
    }
    return render(request, 'billing/inventory_list.html', context)

@login_required
@permission_required('billing.view_supplier', raise_exception=True)
def supplier_list_view(request):
    suppliers = Supplier.objects.prefetch_related(
        Prefetch('purchase_orders', queryset=PurchaseOrder.objects.prefetch_related('payments'))
    ).all().order_by('name')
    category_filter = request.GET.get('category', '')
    if category_filter:
        suppliers = suppliers.filter(category=category_filter)
    context = {
        'suppliers_list': suppliers,
        'page_title': 'Product Suppliers',
        'category_choices': Supplier.SUPPLIER_CATEGORY_CHOICES,
        'category_filter': category_filter
    }
    return render(request, 'billing/supplier_list.html', context)

@login_required
@permission_required('billing.add_supplier', raise_exception=True)
def add_supplier_view(request):
    if request.method == 'POST':
        form = SupplierForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Supplier added successfully!')
            return redirect('billing:supplier_list')
    else:
        form = SupplierForm()
    return render(request, 'billing/supplier_form.html', {'form': form, 'page_title': 'Add New Supplier'})

@login_required
@permission_required('billing.change_supplier', raise_exception=True)
def edit_supplier_view(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    if request.method == 'POST':
        form = SupplierForm(request.POST, instance=supplier)
        if form.is_valid():
            form.save()
            messages.success(request, 'Supplier updated successfully!')
            return redirect('billing:supplier_list')
    else:
        form = SupplierForm(instance=supplier)
    return render(request, 'billing/supplier_form.html', {'form': form, 'supplier': supplier, 'page_title': f'Edit Supplier: {supplier.name}'})

@login_required
@permission_required('billing.delete_supplier', raise_exception=True)
def delete_supplier_view(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    if request.method == 'POST':
        supplier.delete()
        messages.success(request, 'Supplier deleted successfully!')
        return redirect('billing:supplier_list')
    return render(request, 'billing/supplier_confirm_delete.html', {'supplier': supplier, 'page_title': f'Confirm Delete: {supplier.name}'})

@login_required
@permission_required('billing.change_stockitem', raise_exception=True)
@transaction.atomic
def edit_stock_item_view(request, pk):
    stock_item = get_object_or_404(StockItem, pk=pk)
    if not stock_item.purchase_order_item:
        messages.error(request, "This stock item is not linked to a purchase order and cannot be edited from here.")
        return redirect('billing:inventory_list')
    po = stock_item.purchase_order_item.purchase_order
    if request.method == 'POST':
        form = StockItemForm(request.POST, instance=stock_item)
        if form.is_valid():
            form.save()
            messages.success(request, f'Batch "{stock_item.batch_number}" for product "{stock_item.product_variant}" has been updated.')
            return redirect('billing:purchase_order_detail', pk=po.pk)
    else:
        form = StockItemForm(instance=stock_item)
    context = {
        'form': form,
        'stock_item': stock_item,
        'purchase_order': po,
        'page_title': f'Edit Batch: {stock_item.batch_number or "N/A"}'
    }
    return render(request, 'billing/edit_stock_item.html', context)

# =============== INVOICE & PAYMENT VIEWS ===============

@login_required
@permission_required('billing.add_invoice', raise_exception=True)
def create_invoice_view(request, pk=None):
    page_title = 'Create New Invoice'
    initial_data = {}
    if pk:
        appointment = get_object_or_404(Appointment, pk=pk)
        if hasattr(appointment, 'invoice') and appointment.invoice:
            messages.warning(request, f"An invoice ({appointment.invoice.invoice_number}) already exists for this appointment.")
            return redirect('billing:invoice_detail', pk=appointment.invoice.pk)
        initial_data = {'patient': appointment.patient, 'doctor': appointment.doctor, 'appointment': appointment, 'invoice_date': appointment.appointment_datetime.date()}
        page_title = f'Create Invoice for {appointment.patient.name}'

    if request.method == 'POST':
        invoice_form = InvoiceForm(request.POST)
        item_formset = InvoiceItemFormSet(request.POST, prefix='items')
        if invoice_form.is_valid() and item_formset.is_valid():
            with transaction.atomic():
                invoice = invoice_form.save(commit=False)
                invoice.save()
                item_formset.instance = invoice
                item_formset.save()
            messages.success(request, f'Invoice {invoice.invoice_number} created successfully!')
            return redirect('billing:invoice_detail', pk=invoice.pk)
    else:
        invoice_form = InvoiceForm(initial=initial_data)
        item_formset = InvoiceItemFormSet(queryset=InvoiceItem.objects.none(), prefix='items')

    context = {
        'invoice_form': invoice_form, 
        'formset': item_formset, 
        'page_title': page_title,
        'js_data': get_invoice_context_data()
    }
    return render(request, 'billing/invoice_form.html', context)

@login_required
@permission_required('billing.change_invoice', raise_exception=True)
def edit_invoice_view(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if request.method == 'POST':
        invoice_form = InvoiceForm(request.POST, instance=invoice)
        item_formset = InvoiceItemFormSet(request.POST, instance=invoice, prefix='items')
        if invoice_form.is_valid() and item_formset.is_valid():
            with transaction.atomic():
                invoice = invoice_form.save()
                item_formset.save()
            messages.success(request, f'Invoice {invoice.invoice_number} updated successfully!')
            return redirect('billing:invoice_detail', pk=invoice.pk)
    else:
        invoice_form = InvoiceForm(instance=invoice)
        item_formset = InvoiceItemFormSet(instance=invoice, prefix='items')
    context = {'invoice_form': invoice_form, 'formset': item_formset, 'invoice': invoice, 'page_title': f'Edit Invoice: {invoice.invoice_number}', 'js_data': get_invoice_context_data(invoice_instance=invoice)}
    return render(request, 'billing/invoice_form.html', context)

@login_required
@permission_required('billing.view_invoice', raise_exception=True)
def invoice_list_view(request):
    invoices = Invoice.objects.select_related('patient', 'doctor').all()
    status_filter = request.GET.get('status', '')
    if status_filter:
        invoices = invoices.filter(status=status_filter)
    search_query = request.GET.get('q', '').strip()
    if search_query:
        invoices = invoices.filter(Q(invoice_number__icontains=search_query) | Q(patient__name__icontains=search_query))
    context = {'invoices_list': invoices, 'page_title': 'Patient Invoices', 'status_choices': Invoice.STATUS_CHOICES, 'status_filter': status_filter, 'search_query': search_query}
    return render(request, 'billing/invoice_list.html', context)

@login_required
@permission_required('billing.view_invoice', raise_exception=True)
def invoice_detail_view(request, pk):
    invoice = get_object_or_404(Invoice.objects.prefetch_related('payments', 'refunds'), pk=pk)
    context = {'invoice': invoice, 'invoice_items': invoice.invoice_items.all(), 'payments': invoice.payments.all(), 'refunds': invoice.refunds.all(), 'page_title': f'Invoice: {invoice.invoice_number}'}
    return render(request, 'billing/invoice_detail.html', context)

@login_required
@permission_required('billing.add_invoicepayment', raise_exception=True)
def add_invoice_payment_view(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if request.method == 'POST':
        form = InvoicePaymentForm(request.POST, invoice=invoice)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.invoice = invoice
            payment.save()
            messages.success(request, f"Payment of ₹{payment.amount} recorded successfully.")
            return redirect('billing:invoice_detail', pk=invoice.pk)
    else:
        form = InvoicePaymentForm(invoice=invoice)
    context = {'form': form, 'invoice': invoice, 'payments': invoice.payments.all(), 'page_title': f"Add Payment for Invoice {invoice.invoice_number}"}
    return render(request, 'billing/add_invoice_payment.html', context)

@login_required
@permission_required('billing.add_refund', raise_exception=True)
def record_refund_view(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if invoice.balance_due >= 0:
        messages.error(request, "A refund can only be recorded for an overpaid invoice.")
        return redirect('billing:invoice_detail', pk=invoice.pk)

    credit_available = -invoice.balance_due

    if request.method == 'POST':
        form = RefundForm(request.POST, invoice=invoice)
        if form.is_valid():
            refund = form.save(commit=False)
            refund.invoice = invoice
            refund.save()
            messages.success(request, f"Refund of ₹{refund.amount} recorded successfully.")
            return redirect('billing:invoice_detail', pk=invoice.pk)
    else:
        form = RefundForm(invoice=invoice, initial={'amount': credit_available})
        
    context = {
        'form': form, 
        'invoice': invoice, 
        'refunds': invoice.refunds.all(), 
        'credit_available': credit_available, 
        'page_title': f"Record Refund for Invoice {invoice.invoice_number}"
    }
    return render(request, 'billing/record_refund.html', context)

@login_required
@permission_required('billing.view_invoice', raise_exception=True)
def print_invoice_view(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    return render(request, 'billing/invoice_print.html', {'invoice': invoice, 'page_title': f'Print Invoice: {invoice.invoice_number}'})

@login_required
@permission_required('billing.delete_invoice', raise_exception=True)
def delete_invoice_view(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if request.method == 'POST':
        invoice.delete()
        messages.success(request, f'Invoice {invoice.invoice_number} deleted successfully!')
        return redirect('billing:invoice_list')
    return render(request, 'billing/invoice_confirm_delete.html', {'invoice': invoice, 'page_title': f'Confirm Delete: {invoice.invoice_number}'})

# =============== SERVICE & STOCK ADJUSTMENT ===============

@login_required
@permission_required('billing.view_service', raise_exception=True)
def service_list_view(request):
    return render(request, 'billing/service_list.html', {'services_list': Service.objects.all().order_by('name'), 'page_title': 'Clinic Services'})

@login_required
@permission_required('billing.add_service', raise_exception=True)
def add_service_view(request):
    if request.method == 'POST':
        form = ServiceForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Service added successfully!')
            return redirect('billing:service_list')
    else:
        form = ServiceForm()
    return render(request, 'billing/service_form.html', {'form': form, 'page_title': 'Add New Service'})

@login_required
@permission_required('billing.change_service', raise_exception=True)
def edit_service_view(request, pk):
    service = get_object_or_404(Service, pk=pk)
    if request.method == 'POST':
        form = ServiceForm(request.POST, instance=service)
        if form.is_valid():
            form.save()
            messages.success(request, 'Service updated successfully!')
            return redirect('billing:service_list')
    else:
        form = ServiceForm(instance=service)
    return render(request, 'billing/service_form.html', {'form': form, 'service': service, 'page_title': f'Edit Service: {service.name}'})

@login_required
@permission_required('billing.delete_service', raise_exception=True)
def delete_service_view(request, pk):
    service = get_object_or_404(Service, pk=pk)
    if request.method == 'POST':
        service.delete()
        messages.success(request, 'Service deleted successfully!')
        return redirect('billing:service_list')
    return render(request, 'billing/service_confirm_delete.html', {'service': service, 'page_title': f'Confirm Delete: {service.name}'})

@login_required
@permission_required('billing.view_stockadjustment', raise_exception=True)
def stock_adjustment_list_view(request):
    adjustments = StockAdjustment.objects.select_related('product_variant__product').all()
    return render(request, 'billing/stock_adjustment_list.html', {'adjustments_list': adjustments, 'page_title': 'Stock Adjustment History'})

@login_required
@permission_required('billing.add_stockadjustment', raise_exception=True)
@transaction.atomic
def create_stock_adjustment_view(request):
    if request.method == 'POST':
        form = StockAdjustmentForm(request.POST)
        if form.is_valid():
            adjustment = form.save(commit=False)
            adjustment.adjusted_by = request.user
            adjustment.save()
            messages.success(request, f'Stock for "{adjustment.product_variant}" was adjusted successfully.')
            return redirect('billing:stock_adjustment_list')
    else:
        form = StockAdjustmentForm()
    return render(request, 'billing/stock_adjustment_form.html', {'form': form, 'page_title': 'Create Manual Stock Adjustment'})

# =============== SUPPLIER PAYMENT & LOW STOCK ===============

@login_required
@permission_required('billing.add_supplierpayment', raise_exception=True)
def add_supplier_payment_view(request, pk):
    purchase_order = get_object_or_404(PurchaseOrder, pk=pk)
    
    # --- FIX: Fetch available credits for the supplier ---
    available_credits = SupplierCredit.objects.filter(
        supplier=purchase_order.supplier,
        is_fully_used=False
    )
    # --- END OF FIX ---

    if request.method == 'POST':
        form = SupplierPaymentForm(request.POST, purchase_order=purchase_order)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.purchase_order = purchase_order
            payment.save()
            messages.success(request, f"Payment of ₹{payment.amount} recorded successfully.")
            return redirect('billing:add_supplier_payment', pk=purchase_order.pk)
    else:
        form = SupplierPaymentForm(purchase_order=purchase_order, initial={'amount': purchase_order.balance_due})

    context = {
        'form': form,
        'purchase_order': purchase_order,
        'payments': purchase_order.payments.all().order_by('-payment_date'),
        'available_credits': available_credits, # Pass credits to the template
        'page_title': f'Add Payment for {purchase_order.supplier.name} (PO #{purchase_order.pk})'
    }
    return render(request, 'billing/add_supplier_payment.html', context)

@login_required
@permission_required('billing.view_supplierpayment', raise_exception=True)
def supplier_payment_list_view(request):
    payments = SupplierPayment.objects.all().order_by('-payment_date')
    return render(request, 'billing/supplier_payment_list.html', {'payments_list': payments})

@login_required
@permission_required('billing.view_productvariant', raise_exception=True)
def low_stock_report_view(request):
    low_stock_products = [ 
        v for v in ProductVariant.objects.filter(is_active=True) 
        if v.stock_quantity <= v.low_stock_threshold
    ]
    context = {
        'low_stock_products': low_stock_products,
        'page_title': 'Low Stock Report'
    }
    return render(request, 'billing/low_stock_report.html', context)

@login_required
@permission_required('billing.add_supplierpayment', raise_exception=True)
@transaction.atomic
def apply_supplier_credit_view(request, po_pk):
    if request.method == 'POST':
        purchase_order = get_object_or_404(PurchaseOrder, pk=po_pk)
        credit_id = request.POST.get('credit_id')
        amount_to_apply_str = request.POST.get('amount_to_apply')

        if not (credit_id and amount_to_apply_str):
            messages.error(request, "Missing credit or amount information.")
            return redirect('billing:add_supplier_payment', pk=po_pk)

        try:
            amount_to_apply = Decimal(amount_to_apply_str)
            credit = get_object_or_404(SupplierCredit, id=credit_id, supplier=purchase_order.supplier)

            if amount_to_apply <= 0:
                messages.error(request, "Amount to apply must be positive.")
            elif amount_to_apply > credit.balance:
                messages.error(request, f"Cannot apply {amount_to_apply}. Only {credit.balance} is available on this credit note.")
            elif amount_to_apply > purchase_order.balance_due:
                messages.error(request, f"Cannot apply {amount_to_apply}. Only {purchase_order.balance_due} is due on this PO.")
            else:
                # All checks passed, apply the credit
                CreditApplication.objects.create(
                    credit=credit,
                    applied_to_po=purchase_order,
                    amount_applied=amount_to_apply
                )
                
                messages.success(request, f"Successfully applied ₹{amount_to_apply} from credit note #{credit.id}.")

        except (ValueError, TypeError):
            messages.error(request, "Invalid amount entered.")
        except SupplierCredit.DoesNotExist:
            messages.error(request, "Credit note not found or does not belong to this supplier.")

        return redirect('billing:add_supplier_payment', pk=po_pk)
    
    # Redirect GET requests
    return redirect('billing:purchase_order_list')