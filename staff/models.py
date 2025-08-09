# DENTALCLINICSYSTEM/staff/models.py

from django.db import models
from django.conf import settings
from django.utils import timezone
from phonenumber_field.modelfields import PhoneNumberField
from datetime import date

class StaffMember(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='staff_profile'
    )

    # Doctor-specific fields are now part of the StaffMember model
    SPECIALIZATION_CHOICES = [
        ('GD', 'General Dentistry'), ('ORTHO', 'Orthodontics'),
        ('ENDO', 'Endodontics'), ('PERIO', 'Periodontics'),
        ('PROSTHO', 'Prosthodontics'), ('PEDO', 'Pediatric Dentistry'),
        ('OS', 'Oral Surgery'), ('OTHER', 'Other'),
    ]
    specialization = models.CharField(
        max_length=10,
        choices=SPECIALIZATION_CHOICES,
        blank=True,
        null=True
    )
    credentials = models.TextField(blank=True, null=True)

    # Existing staff fields
    contact_number = PhoneNumberField(unique=True, null=True, blank=True)
    address = models.TextField(blank=True, null=True)
    date_of_birth = models.DateField(null=True, blank=True)
    date_joined = models.DateField(default=timezone.now)
    is_active = models.BooleanField(default=True)

    @property
    def name(self):
        return self.user.get_full_name()

    @property
    def age(self):
        if self.date_of_birth:
            today = date.today()
            return today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
        return None

    def __str__(self):
        # Display "Dr." prefix if the user is in the "Doctors" group
        if self.user.groups.filter(name='Doctors').exists():
            return f"Dr. {self.name}"
        return self.name

    def save(self, *args, **kwargs):
        # Sync is_active status with the user model
        if self.user.is_active != self.is_active:
            self.user.is_active = self.is_active
            self.user.save()

        super().save(*args, **kwargs)

    class Meta:
        ordering = ['user__first_name', 'user__last_name']