# DENTALCLINICSYSTEM/lab_cases/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import ProtectedError
from django.contrib import messages
from django.core.exceptions import ValidationError
from .models import DentalLab, LabCase
from .forms import DentalLabForm, LabCaseForm, LabCaseFilterForm, LabPaymentForm
from appointments.models import Appointment
from decimal import Decimal, ROUND_HALF_UP

@login_required
@permission_required('lab_cases.view_dentallab', raise_exception=True)
def lab_list_view(request):
    all_labs = DentalLab.objects.all()
    context = {
        'labs_list': all_labs,
        'page_title': 'Dental Laboratories'
    }
    return render(request, 'lab_cases/lab_list.html', context)

@login_required
@permission_required('lab_cases.add_dentallab', raise_exception=True)
def add_lab_view(request):
    if request.method == 'POST':
        form = DentalLabForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'New dental lab added successfully!')
            return redirect('lab_cases:lab_list')
    else:
        form = DentalLabForm()

    context = {
        'form': form,
        'page_title': 'Add New Dental Lab'
    }
    return render(request, 'lab_cases/add_lab.html', context)

@login_required
@permission_required('lab_cases.change_dentallab', raise_exception=True)
def edit_lab_view(request, pk):
    lab_to_edit = get_object_or_404(DentalLab, pk=pk)

    if request.method == 'POST':
        form = DentalLabForm(request.POST, instance=lab_to_edit)
        if form.is_valid():
            form.save()
            messages.success(request, f"'{lab_to_edit.name}' updated successfully!")
            return redirect('lab_cases:lab_list')
    else:
        form = DentalLabForm(instance=lab_to_edit)

    context = {
        'form': form,
        'lab': lab_to_edit,
        'page_title': f'Edit Lab: {lab_to_edit.name}'
    }
    return render(request, 'lab_cases/edit_lab.html', context)

@login_required
@permission_required('lab_cases.delete_dentallab', raise_exception=True)
def delete_lab_view(request, pk):
    lab_to_delete = get_object_or_404(DentalLab, pk=pk)

    if request.method == 'POST':
        try:
            lab_to_delete.delete()
            messages.success(request, f"The lab '{lab_to_delete.name}' was deleted successfully.")
        except ProtectedError:
            messages.error(
                request,
                f"The lab '{lab_to_delete.name}' cannot be deleted because it is linked to one or more existing lab cases."
            )
        return redirect('lab_cases:lab_list')

    context = {
        'lab': lab_to_delete,
        'page_title': f'Confirm Delete: {lab_to_delete.name}'
    }
    return render(request, 'lab_cases/lab_confirm_delete.html', context)

@login_required
@permission_required('lab_cases.view_labcase', raise_exception=True)
def lab_case_list_view(request):
    all_cases = LabCase.objects.select_related('patient', 'doctor', 'lab').all()
    
    filter_form = LabCaseFilterForm(request.GET)
    if filter_form.is_valid():
        status = filter_form.cleaned_data.get('status')
        lab = filter_form.cleaned_data.get('lab')
        start_date = filter_form.cleaned_data.get('start_date')
        end_date = filter_form.cleaned_data.get('end_date')

        if status:
            all_cases = all_cases.filter(status=status)
        if lab:
            all_cases = all_cases.filter(lab=lab)
        if start_date:
            all_cases = all_cases.filter(date_sent__gte=start_date)
        if end_date:
            all_cases = all_cases.filter(date_sent__lte=end_date)
            
    context = {
        'lab_cases_list': all_cases,
        'page_title': 'Lab Cases',
        'filter_form': filter_form,
    }
    return render(request, 'lab_cases/lab_case_list.html', context)

@login_required
@permission_required('lab_cases.add_labcase', raise_exception=True)
def add_lab_case_view(request, pk=None):
    initial_data = {}
    appointment = None
    if pk:
        appointment = get_object_or_404(Appointment, pk=pk)
        initial_data = {
            'patient': appointment.patient,
            'doctor': appointment.doctor,
        }

    if request.method == 'POST':
        form = LabCaseForm(request.POST)  # Correct: no initial in POST
        if form.is_valid():
            new_case = form.save()
            messages.success(request, 'New lab case logged successfully!')
            if appointment:
                return redirect('appointments:appointment_detail', pk=appointment.pk)
            return redirect('lab_cases:lab_case_detail', pk=new_case.pk)
    else:
        form = LabCaseForm(initial=initial_data)

    context = {
        'form': form,
        'page_title': 'Log New Lab Case',
        'appointment': appointment,
    }
    return render(request, 'lab_cases/add_lab_case.html', context)

@login_required
@permission_required('lab_cases.view_labcase', raise_exception=True)
def lab_case_detail_view(request, pk):
    lab_case = get_object_or_404(LabCase.objects.prefetch_related('payments'), pk=pk)
    context = {
        'case': lab_case,
        'payments': lab_case.payments.all(),
        'page_title': f"Details for Lab Case: {lab_case.case_type} for {lab_case.patient.name}"
    }
    return render(request, 'lab_cases/lab_case_detail.html', context)

@login_required
@permission_required('lab_cases.change_labcase', raise_exception=True)
def edit_lab_case_view(request, pk):
    case_to_edit = get_object_or_404(LabCase, pk=pk)

    if case_to_edit.amount_paid > 0 or case_to_edit.status in ['COMPLETED', 'CANCELLED']:
        messages.error(request, "This lab case cannot be edited because it has been paid for or is in a final state (Completed/Cancelled).")
        return redirect('lab_cases:lab_case_detail', pk=case_to_edit.pk)

    if request.method == 'POST':
        form = LabCaseForm(request.POST, instance=case_to_edit)
        if form.is_valid():
            form.save()
            messages.success(request, 'Lab case updated successfully!')
            return redirect('lab_cases:lab_case_detail', pk=case_to_edit.pk)
    else:
        form = LabCaseForm(instance=case_to_edit)

    context = {
        'form': form,
        'case': case_to_edit,
        'page_title': f'Edit Lab Case for {case_to_edit.patient.name}'
    }
    return render(request, 'lab_cases/edit_lab_case.html', context)

@login_required
@permission_required('lab_cases.delete_labcase', raise_exception=True)
def delete_lab_case_view(request, pk):
    case_to_delete = get_object_or_404(LabCase, pk=pk)

    if case_to_delete.amount_paid > 0 or case_to_delete.status in ['COMPLETED', 'CANCELLED']:
        messages.error(request, "This lab case cannot be deleted because it has payments or has been completed/cancelled.")
        return redirect('lab_cases:lab_case_detail', pk=case_to_delete.pk)

    if request.method == 'POST':
        case_to_delete.delete()
        messages.success(request, "The lab case was deleted successfully.")
        return redirect('lab_cases:lab_case_list')

    context = {
        'case': case_to_delete,
        'page_title': f'Confirm Delete Lab Case for {case_to_delete.patient.name}'
    }
    return render(request, 'lab_cases/lab_case_confirm_delete.html', context)

@login_required
@permission_required('lab_cases.add_labpayment', raise_exception=True)
def add_lab_payment_view(request, pk):
    lab_case = get_object_or_404(LabCase, pk=pk)
    
    if request.method == 'POST':
        form = LabPaymentForm(request.POST, lab_case=lab_case)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.lab_case = lab_case
            try:
                payment.save()
                messages.success(request, f"Payment of ₹{payment.amount} recorded successfully.")
                return redirect('lab_cases:lab_case_detail', pk=lab_case.pk)
            except ValidationError as e:
                form.add_error('amount', e.message)
    else:
        balance = lab_case.balance_due.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        form = LabPaymentForm(initial={'amount': balance}, lab_case=lab_case)

    context = {
        'form': form,
        'case': lab_case,
        'payments': lab_case.payments.all(),
        'page_title': f"Add Payment for Case #{lab_case.pk}"
    }
    return render(request, 'lab_cases/add_lab_payment.html', context)