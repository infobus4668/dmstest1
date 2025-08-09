# DENTALCLINICSYSTEM/reporting/views.py

from django.shortcuts import render
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Sum, Q
from billing.models import Invoice, StockItem, SupplierPayment, InvoicePayment, Refund
from lab_cases.models import LabCase
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal
from .forms import ReportFilterForm

@login_required
@permission_required('staff.view_staffmember', raise_exception=True)
def report_index_view(request):
    context = {'page_title': 'Reports'}
    return render(request, 'reporting/report_index.html', context)


@login_required
@permission_required('staff.view_staffmember', raise_exception=True)
def financial_summary_report(request):
    today = timezone.now().date()
    start_of_month = today.replace(day=1)
    
    next_month = (start_of_month + timedelta(days=32)).replace(day=1)
    end_of_month = next_month - timedelta(days=1)

    total_paid_this_month = InvoicePayment.objects.filter(
        payment_date__gte=start_of_month,
        payment_date__lte=end_of_month
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    invoices_this_month = Invoice.objects.filter(
        invoice_date__gte=start_of_month,
        invoice_date__lte=end_of_month
    ).exclude(status__in=['CANCELLED', 'DRAFT'])
    
    total_invoiced_this_month = invoices_this_month.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')

    all_active_invoices = Invoice.objects.exclude(status__in=['DRAFT', 'CANCELLED'])
    total_outstanding_balance = sum(invoice.balance_due for invoice in all_active_invoices)

    context = {
        'page_title': 'Financial Summary Report',
        'report_month': start_of_month.strftime("%B %Y"),
        'total_invoiced_this_month': total_invoiced_this_month,
        'total_paid_this_month': total_paid_this_month,
        'total_outstanding_balance': total_outstanding_balance,
    }
    return render(request, 'reporting/financial_summary.html', context)


@login_required
@permission_required('staff.view_staffmember', raise_exception=True)
def stock_received_report_view(request):
    form = ReportFilterForm(request.GET or None, hide_lab=True, hide_patient=True, hide_status=True)
    stock_items = StockItem.objects.select_related('product_variant', 'supplier').order_by('-date_received')

    if form.is_valid():
        date_range_str = form.cleaned_data.get('date_range')
        product = form.cleaned_data.get('product')
        supplier = form.cleaned_data.get('supplier')

        if date_range_str:
            try:
                start_date_str, end_date_str = date_range_str.split(' - ')
                start_date = datetime.strptime(start_date_str, '%d/%m/%Y').date()
                end_date = datetime.strptime(end_date_str, '%d/%m/%Y').date()
                stock_items = stock_items.filter(date_received__date__range=[start_date, end_date])
            except (ValueError, TypeError):
                pass
        if product:
            stock_items = stock_items.filter(product_variant__product=product)
        if supplier:
            stock_items = stock_items.filter(supplier=supplier)

    context = {
        'form': form,
        'stock_items': stock_items,
        'page_title': 'Stock Received Report'
    }
    return render(request, 'reporting/stock_received_report.html', context)


@login_required
@permission_required('staff.view_staffmember', raise_exception=True)
def supplier_payment_report_view(request):
    form = ReportFilterForm(request.GET or None, hide_product=True, hide_lab=True, hide_patient=True, hide_status=True)
    payments = SupplierPayment.objects.select_related('purchase_order__supplier').order_by('-payment_date')
    total_paid = 0

    if form.is_valid():
        date_range_str = form.cleaned_data.get('date_range')
        supplier = form.cleaned_data.get('supplier')

        if date_range_str:
            try:
                start_date_str, end_date_str = date_range_str.split(' - ')
                start_date = datetime.strptime(start_date_str, '%d/%m/%Y').date()
                end_date = datetime.strptime(end_date_str, '%d/%m/%Y').date()
                payments = payments.filter(payment_date__range=[start_date, end_date])
            except (ValueError, TypeError):
                pass
        if supplier:
            payments = payments.filter(purchase_order__supplier=supplier)

        total_paid = payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    context = {
        'form': form,
        'payments': payments,
        'total_paid': total_paid,
        'page_title': 'Supplier Payment Report'
    }
    return render(request, 'reporting/supplier_payment_report.html', context)


@login_required
@permission_required('staff.view_staffmember', raise_exception=True)
def lab_cases_report_view(request):
    form = ReportFilterForm(request.GET or None, hide_supplier=True, hide_product=True)
    lab_cases = LabCase.objects.select_related('patient', 'doctor', 'lab').order_by('-created_at')

    if form.is_valid():
        date_range_str = form.cleaned_data.get('date_range')
        lab = form.cleaned_data.get('lab')
        patient = form.cleaned_data.get('patient')
        status = form.cleaned_data.get('status')

        if date_range_str:
            try:
                start_date_str, end_date_str = date_range_str.split(' - ')
                start_date = datetime.strptime(start_date_str, '%d/%m/%Y').date()
                end_date = datetime.strptime(end_date_str, '%d/%m/%Y').date()
                lab_cases = lab_cases.filter(created_at__date__range=[start_date, end_date])
            except (ValueError, TypeError):
                pass
        
        if lab:
            lab_cases = lab_cases.filter(lab=lab)
        if patient:
            lab_cases = lab_cases.filter(patient=patient)
        if status:
            lab_cases = lab_cases.filter(status=status)
    
    total_cost = sum(case.total_cost for case in lab_cases if case.total_cost)
    total_paid = sum(case.amount_paid for case in lab_cases)
    total_balance = total_cost - total_paid

    context = {
        'form': form,
        'lab_cases': lab_cases,
        'page_title': 'Lab Cases Report',
        'total_cost': total_cost,
        'total_paid': total_paid,
        'total_balance': total_balance,
    }
    return render(request, 'reporting/lab_cases_report.html', context)