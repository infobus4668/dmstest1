from django.db import models
from appointments.models import Appointment


# --- Existing DentalRecord Model ---
class DentalRecord(models.Model):
    appointment = models.OneToOneField(
        Appointment,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='dental_record'
    )
    
    clinical_notes = models.TextField(
        blank=True, 
        null=True,
        help_text="Doctor's clinical notes, observations, diagnosis for this visit."
    )
    
    treatments_performed = models.TextField(
        blank=True, 
        null=True,
        help_text="Details of treatments performed during this visit (e.g., 'Scaling and Polishing', 'Composite filling on #24 MOD')."
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        appointment_datetime_str = self.appointment.appointment_datetime.strftime("%Y-%m-%d %I:%M %p")
        return f"Dental Record for Appointment: {self.appointment.patient.name} with Dr. {self.appointment.doctor.name} on {appointment_datetime_str}"

    class Meta:
        verbose_name = "Dental Record"
        verbose_name_plural = "Dental Records"


# --- NEW: Prescription Models ---
class Prescription(models.Model):
    dental_record = models.OneToOneField(
        DentalRecord,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='prescription'
    )
    date_prescribed = models.DateField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True, help_text="General notes for the entire prescription.")
    
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Prescription for {self.dental_record.appointment.patient.name} on {self.date_prescribed}"

    class Meta:
        verbose_name = "Prescription"
        verbose_name_plural = "Prescriptions"


class PrescriptionItem(models.Model):
    prescription = models.ForeignKey(
        Prescription,
        on_delete=models.CASCADE,
        related_name='items'
    )
    medication_name = models.CharField(max_length=200)
    dosage = models.CharField(max_length=100, blank=True, help_text="e.g., '500mg', '1 tablet'")
    frequency = models.CharField(max_length=100, blank=True, help_text="e.g., '3 times a day', 'Once at night'")
    duration = models.CharField(max_length=100, blank=True, help_text="e.g., 'for 5 days', 'for 1 week'")
    notes = models.TextField(blank=True, null=True, help_text="Specific instructions for this medication.")

    def __str__(self):
        return f"{self.medication_name} ({self.dosage})"

    class Meta:
        verbose_name = "Prescription Item"
        verbose_name_plural = "Prescription Items"


def dental_image_path(instance, filename):
    # Uses patient primary key for path normalization
    patient_pk = instance.dental_record.appointment.patient.pk
    return f'patient_images/patient_{patient_pk}/{filename}'


class DentalImage(models.Model):
    dental_record = models.ForeignKey(
        DentalRecord,
        on_delete=models.CASCADE,
        related_name='images'
    )
    image = models.ImageField(upload_to=dental_image_path)
    caption = models.CharField(max_length=255, blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for {self.dental_record.appointment.patient.name} - {self.caption or 'No caption'}"
