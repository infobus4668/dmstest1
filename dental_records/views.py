import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.urls import reverse
from django.db import transaction, DatabaseError, IntegrityError
from django.core.exceptions import ValidationError
from django.contrib.auth.decorators import login_required, permission_required

from .models import DentalRecord, DentalImage, Prescription
from .forms import DentalRecordForm, PrescriptionForm, PrescriptionItemFormSet
from appointments.models import Appointment

logger = logging.getLogger(__name__)

@login_required
@permission_required('dental_records.change_dentalrecord', raise_exception=True)
def manage_dental_record_view(request, pk):
    """
    Manages the creation, updating, and image handling for a DentalRecord
    linked to a specific appointment.
    """
    appointment = get_object_or_404(Appointment, pk=pk)
    # get_or_create handles both adding and editing a record seamlessly.
    record, created = DentalRecord.objects.get_or_create(appointment=appointment)

    if request.method == 'POST':
        form = DentalRecordForm(request.POST, instance=record)
        
        # --- Action: Delete an existing image ---
        if 'delete_image' in request.POST:
            image_id = request.POST.get('delete_image')
            try:
                # Permission to delete an image is tied to changing the parent record.
                image = DentalImage.objects.get(pk=image_id, dental_record=record)
                image.delete()
                messages.success(request, 'Image deleted successfully!')
            except DentalImage.DoesNotExist:
                messages.error(request, 'Image not found or you do not have permission to delete it.')
            return redirect('dental_records:manage_dental_record', pk=appointment.pk)

        # --- Action: Upload a new image separately ---
        elif 'upload_image' in request.POST:
            image_file = request.FILES.get('image')
            caption = request.POST.get('caption', '')
            if image_file:
                DentalImage.objects.create(
                    dental_record=record,
                    image=image_file,
                    caption=caption
                )
                messages.success(request, 'Image uploaded successfully!')
            else:
                messages.error(request, 'No image file was selected.')
            return redirect('dental_records:manage_dental_record', pk=appointment.pk)

        # --- Default Action: Save the main record details (and optionally a new image) ---
        else:
            if form.is_valid():
                form.save()
                
                image_file = request.FILES.get('image')
                caption = request.POST.get('caption', '')
                
                if image_file:
                    DentalImage.objects.create(
                        dental_record=record,
                        image=image_file,
                        caption=caption
                    )
                    messages.success(request, 'Dental record and new image saved successfully!')
                else:
                    messages.success(request, 'Dental record saved successfully!')
                
                return redirect('dental_records:manage_dental_record', pk=appointment.pk)
            else:
                messages.error(request, 'Please correct the errors below.')

    else:
        form = DentalRecordForm(instance=record)

    context = {
        'form': form,
        'appointment': appointment,
        'record': record,
        'images': record.images.all(),
        'page_title': f"Manage Dental Record for {appointment.patient.name}",
    }
    return render(request, 'dental_records/manage_dental_record.html', context)


@login_required
@permission_required('dental_records.change_prescription', raise_exception=True)
def manage_prescription_view(request, pk):
    appointment = get_object_or_404(Appointment, pk=pk)
    dental_record, __ = DentalRecord.objects.get_or_create(appointment=appointment)

    try:
        prescription = dental_record.prescription
    except Prescription.DoesNotExist:
        prescription = None

    if request.method == 'POST':
        prescription_form = PrescriptionForm(request.POST, instance=prescription, prefix='presc')
        item_formset = PrescriptionItemFormSet(request.POST, instance=prescription, prefix='items')

        if prescription_form.is_valid() and item_formset.is_valid():
            try:
                with transaction.atomic():
                    saved_prescription = prescription_form.save(commit=False)
                    saved_prescription.dental_record = dental_record
                    saved_prescription.save()

                    item_formset.instance = saved_prescription
                    item_formset.save()

                    messages.success(request, 'Prescription saved successfully!')
                    return redirect(reverse('appointments:appointment_detail', kwargs={'pk': appointment.pk}))
            except (DatabaseError, IntegrityError, ValidationError) as e:
                logger.error(f"Error saving prescription for appointment {appointment.pk}: {e}", exc_info=True)
                messages.error(request, "A database error occurred while saving the prescription. Please try again or contact support.")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        prescription_form = PrescriptionForm(instance=prescription, prefix='presc')
        item_formset = PrescriptionItemFormSet(instance=prescription, prefix='items')

    context = {
        'prescription_form': prescription_form,
        'item_formset': item_formset,
        'appointment': appointment,
        'page_title': f"Manage Prescription for {appointment.patient.name}"
    }
    return render(request, 'dental_records/manage_prescription.html', context)


@login_required
@permission_required('dental_records.view_prescription', raise_exception=True)
def prescription_print_view(request, pk):
    prescription = get_object_or_404(
        Prescription.objects.select_related(
            'dental_record__appointment__patient',
            'dental_record__appointment__doctor'
        ),
        pk=pk
    )
    return render(request, 'dental_records/prescription_print.html', {
        'prescription': prescription,
        'page_title': f"Prescription for {prescription.dental_record.appointment.patient.name}",
    })