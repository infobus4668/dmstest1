# DENTALCLINICSYSTEM/appointments/models.py

from django.db import models
from django.utils import timezone
from patients.models import Patient
from staff.models import StaffMember

class Appointment(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='appointments')

    # This is the final corrected field definition
    doctor = models.ForeignKey(
        StaffMember,
        on_delete=models.PROTECT,
        null=True, # Keeps the field optional
        blank=True, # Allows the field to be blank in forms
        limit_choices_to={'user__groups__name': 'Doctors'},
        related_name='appointments'
    )

    appointment_datetime = models.DateTimeField()
    reason = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    STATUS_CHOICES = [
        ('SCH', 'Scheduled'),
        ('CNF', 'Confirmed'),
        ('CMP', 'Completed'),
        ('CAN', 'Cancelled'),
        ('NOS', 'No Show'),
    ]
    status = models.CharField(max_length=3, choices=STATUS_CHOICES, default='SCH')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Appointment for {self.patient.name} on {self.appointment_datetime.strftime('%Y-%m-%d %H:%M')}"

    class Meta:
        ordering = ['-appointment_datetime']