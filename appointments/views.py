# DENTALCLINICSYSTEM/appointments/views.py

from django.http import JsonResponse
from django.urls import reverse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta

from .models import Appointment
from .forms import AppointmentForm
from dental_records.models import DentalRecord, Prescription
from patients.models import Patient
from billing.models import Invoice

# --- API VIEW ---
# Uses Django's permission system for secure access control
@login_required
def appointment_api_view(request):
    user = request.user
    if user.is_superuser or user.has_perm('appointments.view_appointment'):
        all_appointments = Appointment.objects.select_related('patient', 'doctor').all()
    else:
        all_appointments = Appointment.objects.none()

    events = [
        {
            'title': appointment.patient.name,
            'start': appointment.appointment_datetime.isoformat(),
            'end': (appointment.appointment_datetime + timedelta(minutes=45)).isoformat(),
            'url': reverse('appointments:appointment_detail', kwargs={'pk': appointment.pk}),
            'color': '#28a745' if appointment.status == 'CMP' else '#17a2b8',
            'extendedProps': {
                'patient': appointment.patient.name,
                'doctor': str(appointment.doctor),
                'time': appointment.appointment_datetime.strftime('%I:%M %p'),
                'reason': appointment.reason or 'No reason provided'
            }
        }
        for appointment in all_appointments
    ]
    return JsonResponse(events, safe=False)

# --- List View ---
@login_required
@permission_required('appointments.view_appointment', raise_exception=True)
def appointment_list_view(request):
    user = request.user
    if hasattr(user, 'doctor_profile') and not user.is_superuser:
        all_appointments = Appointment.objects.filter(doctor=user.doctor_profile).order_by('-appointment_datetime')
    else:
        all_appointments = Appointment.objects.order_by('-appointment_datetime')

    context = {
        'appointments_list': all_appointments,
        'page_title': 'List of Appointments'
    }
    return render(request, 'appointments/appointment_list.html', context)

# --- Schedule ---
@login_required
@permission_required('appointments.add_appointment', raise_exception=True)
def schedule_appointment_view(request):
    initial_data = {}
    patient_pk = request.GET.get('pk')
    if patient_pk:
        try:
            patient = Patient.objects.get(pk=patient_pk)
            initial_data['patient'] = patient
        except Patient.DoesNotExist:
            pass

    if request.method == 'POST':
        form = AppointmentForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Appointment scheduled successfully!')
            return redirect('appointments:appointment_list')
    else:
        form = AppointmentForm(initial=initial_data)

    return render(request, 'appointments/schedule_appointment.html', {
        'form': form,
        'page_title': 'Schedule New Appointment'
    })

# --- Detail View ---
@login_required
@permission_required('appointments.view_appointment', raise_exception=True)
def appointment_detail_view(request, pk):
    appointment = get_object_or_404(Appointment, pk=pk)
    user = request.user

    is_the_doctor = hasattr(user, 'doctor_profile') and user.doctor_profile == appointment.doctor
    if not request.user.has_perm('staff.view_staffmember') and not is_the_doctor:
        messages.error(request, "You do not have permission to view this specific appointment.")
        return redirect('dashboard')

    try:
        dental_record = appointment.dental_record
    except (DentalRecord.DoesNotExist, AttributeError):
        dental_record = None

    return render(request, 'appointments/appointment_detail.html', {
        'appointment': appointment,
        'dental_record': dental_record,
        'page_title': f"Appointment Details for {appointment.patient.name}"
    })

# --- Edit ---
@login_required
@permission_required('appointments.change_appointment', raise_exception=True)
def edit_appointment_view(request, pk):
    appointment_to_edit = get_object_or_404(Appointment, pk=pk)

    if request.method == 'POST':
        form = AppointmentForm(request.POST, instance=appointment_to_edit)
        if form.is_valid():
            form.save()
            messages.success(request, 'Appointment details updated successfully!')
            return redirect('appointments:appointment_detail', pk=appointment_to_edit.pk)
    else:
        form = AppointmentForm(instance=appointment_to_edit)

    return render(request, 'appointments/edit_appointment.html', {
        'form': form,
        'appointment': appointment_to_edit,
        'page_title': 'Edit Appointment'
    })

# --- Delete ---
@login_required
@permission_required('appointments.delete_appointment', raise_exception=True)
def delete_appointment_view(request, pk):
    appointment_to_delete = get_object_or_404(Appointment, pk=pk)
    if request.method == 'POST':
        appointment_to_delete.delete()
        messages.success(request, 'Appointment deleted successfully!')
        return redirect('appointments:appointment_list')

    return render(request, 'appointments/appointment_confirm_delete.html', {
        'appointment': appointment_to_delete,
        'page_title': 'Confirm Delete'
    })

# --- Print Summary ---
@login_required
@permission_required('appointments.view_appointment', raise_exception=True)
def print_summary_view(request, pk):
    appointment = get_object_or_404(Appointment, pk=pk)

    context = {
        'appointment': appointment,
        'page_title': f'Summary for {appointment.patient.name} on {appointment.appointment_datetime.date()}'
    }

    try:
        invoice = appointment.invoice
        context['invoice'] = invoice
        context['invoice_items'] = invoice.invoice_items.all()
    except (Invoice.DoesNotExist, AttributeError):
        context['invoice'] = None
        context['invoice_items'] = None

    try:
        prescription = appointment.dental_record.prescription
        context['prescription'] = prescription
        context['prescription_items'] = prescription.items.all()
    except (DentalRecord.DoesNotExist, Prescription.DoesNotExist, AttributeError):
        context['prescription'] = None
        context['prescription_items'] = None

    return render(request, 'appointments/print_summary.html', context)

# --- Print Bill Summary ---
@login_required
@permission_required('appointments.view_appointment', raise_exception=True)
def print_bill_summary_view(request, pk):
    appointment = get_object_or_404(
        Appointment.objects.select_related('patient', 'doctor'),
        pk=pk
    )

    context = {
        'appointment': appointment,
        'page_title': f'Bill for {appointment.patient.name} on {appointment.appointment_datetime.date()}'
    }

    try:
        invoice = Invoice.objects.get(appointment=appointment)
        invoice_items = invoice.invoice_items.all()
        context['invoice'] = invoice
        context['services_list'] = invoice_items.filter(service__isnull=False)
        context['products_list'] = invoice_items.filter(stock_item__isnull=False)
    except Invoice.DoesNotExist:
        context['invoice'] = None
        context['services_list'] = []
        context['products_list'] = []

    try:
        prescription = appointment.dental_record.prescription
        context['prescription'] = prescription
        context['prescription_items'] = prescription.items.all()
    except (DentalRecord.DoesNotExist, Prescription.DoesNotExist, AttributeError):
        context['prescription'] = None
        context['prescription_items'] = []

    return render(request, 'appointments/print_bill_summary.html', context)
