# DENTALCLINICSYSTEM/lab_cases/models.py

from django.db import models
from django.utils import timezone
from patients.models import Patient
from staff.models import StaffMember
from decimal import Decimal
from django.core.validators import MinValueValidator
from billing.models import SupplierPayment
from django.core.exceptions import ValidationError
from phonenumber_field.modelfields import PhoneNumberField # Added import

class DentalLab(models.Model):
    name = models.CharField(max_length=200, unique=True)
    contact_person = models.CharField(max_length=100, blank=True, null=True)
    contact_number = PhoneNumberField(blank=True, null=True, unique=True) # Changed to PhoneNumberField and added unique
    email = models.EmailField(max_length=100, blank=True, null=True, unique=True) # Added unique=True
    address = models.TextField(blank=True, null=True)
    notes = models.TextField(
        blank=True,
        null=True,
        help_text="Notes about the lab, like specialties or turnaround times."
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Is this lab currently used by the clinic?"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Dental Lab"
        verbose_name_plural = "Dental Labs"
        ordering = ['name']

    def __str__(self):
        return self.name

class LabCase(models.Model):
    CASE_STATUS_CHOICES = [
        ('CREATED', 'Case Created'),
        ('SENT', 'Sent to Lab'),
        ('RECEIVED', 'Received from Lab'),
        ('COMPLETED', 'Completed / Fitted'),
        ('CANCELLED', 'Cancelled'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name='lab_cases')
    doctor = models.ForeignKey(
        StaffMember,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        limit_choices_to={'user__groups__name': 'Doctors'},
        related_name='lab_cases'
    )
    lab = models.ForeignKey(
        DentalLab,
        on_delete=models.PROTECT,
        related_name='cases',
        help_text="The dental lab this case was sent to."
    )
    case_type = models.CharField(
        max_length=100,
        help_text="e.g., 'Zirconia Crown', 'PFM Bridge', 'Complete Denture'"
    )
    description = models.TextField(
        help_text="Detailed instructions for the lab, including tooth numbers, shade, materials, etc."
    )
    status = models.CharField(
        max_length=10,
        choices=CASE_STATUS_CHOICES,
        default='CREATED'
    )
    cost_per_unit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Cost per unit for the lab work."
    )
    units = models.PositiveIntegerField(
        default=1,
        help_text="Number of units for this case (e.g., number of crowns).",
        validators=[MinValueValidator(1)]
    )
    gst_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        help_text="GST percentage to be applied to the subtotal."
    )
    date_sent = models.DateField(null=True, blank=True)
    date_due = models.DateField(
        null=True,
        blank=True,
        help_text="Expected return date from the lab."
    )
    date_received = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def subtotal(self):
        """Calculate the total cost before tax."""
        return (self.cost_per_unit or 0) * self.units

    @property
    def gst_amount(self):
        """Calculate the GST amount based on the subtotal."""
        return self.subtotal * (self.gst_percentage / 100)

    @property
    def total_cost(self):
        """The final total amount including GST."""
        return self.subtotal + self.gst_amount

    @property
    def amount_paid(self):
        return self.payments.aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')

    @property
    def balance_due(self):
        return self.total_cost - self.amount_paid

    @property
    def is_overdue(self):
        """Check if the case is past its due date and not yet received."""
        return self.date_due and self.date_due < timezone.now().date() and not self.date_received

class LabPayment(models.Model):
    lab_case = models.ForeignKey(LabCase, on_delete=models.CASCADE, related_name='payments')
    payment_date = models.DateTimeField(default=timezone.now)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    payment_method = models.CharField(max_length=20, choices=SupplierPayment.PAYMENT_METHODS, default='BANK')
    notes = models.TextField(blank=True, null=True, help_text="Add transaction ID or other details.")

    class Meta:
        ordering = ['-payment_date']

    def __str__(self):
        return f"Payment of {self.amount} for Lab Case #{self.lab_case.pk}"

    def save(self, *args, **kwargs):
        # Model-level overpayment protection
        if self.lab_case:
            # Exclude current payment when updating, only applies to new
            total_paid = self.lab_case.payments.exclude(pk=self.pk).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
            if self.amount + total_paid > self.lab_case.total_cost:
                raise ValidationError(f"Payment cannot exceed the balance due of ₹{self.lab_case.balance_due:.2f}")
        super().save(*args, **kwargs)