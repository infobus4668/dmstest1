# DENTALCLINICSYSTEM/patients/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from .models import Patient
from .forms import PatientForm
from django.contrib import messages
from django.db import models

@login_required
@permission_required('patients.view_patient', raise_exception=True)
def patient_list(request):
    """Display a list of all patients, with optional search."""
    search_query = request.GET.get('q', '').strip()
    patients = Patient.objects.all()
    if search_query:
        patients = patients.filter(
            models.Q(name__icontains=search_query) |
            models.Q(contact_number__icontains=search_query)
        )
    return render(
        request,
        'patients/patient_list.html',
        {
            'patients_list': patients,
            'search_query': search_query,
            'page_title': 'Patients'
        }
    )

@login_required
@permission_required('patients.view_patient', raise_exception=True)
def patient_detail(request, pk):
    """Display details of a specific patient."""
    patient = get_object_or_404(Patient, pk=pk)
    return render(request, 'patients/patient_detail.html', {'patient': patient})

@login_required
@permission_required('patients.add_patient', raise_exception=True)
def add_patient(request):
    """Handle the creation of a new patient."""
    if request.method == 'POST':
        form = PatientForm(request.POST)
        if form.is_valid():
            # Create instance but don't save to DB yet
            patient = form.save(commit=False)
            # Assign the manually cleaned contact_number
            patient.contact_number = form.cleaned_data.get('contact_number')
            # Now save the instance
            patient.save()
            
            messages.success(request, f'Patient "{patient.name}" has been successfully added.')
            return redirect('patients:patient_list')
    else:
        form = PatientForm()
    return render(request, 'patients/add_patient.html', {'form': form, 'title': 'Add New Patient'})

@login_required
@permission_required('patients.change_patient', raise_exception=True)
def edit_patient(request, pk):
    """Handle editing of an existing patient's details."""
    patient = get_object_or_404(Patient, pk=pk)
    if request.method == 'POST':
        form = PatientForm(request.POST, instance=patient)
        if form.is_valid():
            # Create instance but don't save to DB yet
            edited_patient = form.save(commit=False)
            # Assign the manually cleaned contact_number
            edited_patient.contact_number = form.cleaned_data.get('contact_number')
            # Now save the instance
            edited_patient.save()

            messages.success(request, f'Patient "{patient.name}" has been successfully updated.')
            return redirect('patients:patient_detail', pk=patient.pk)
    else:
        form = PatientForm(instance=patient)
    return render(request, 'patients/edit_patient.html', {'form': form, 'patient': patient, 'title': 'Edit Patient'})

@login_required
@permission_required('patients.delete_patient', raise_exception=True)
def delete_patient(request, pk):
    """Handle deletion of a patient."""
    patient = get_object_or_404(Patient, pk=pk)
    if request.method == 'POST':
        patient_name = patient.name
        patient.delete()
        messages.success(request, f'Patient "{patient_name}" has been successfully deleted.')
        return redirect('patients:patient_list')
    return render(request, 'patients/patient_confirm_delete.html', {'patient': patient})