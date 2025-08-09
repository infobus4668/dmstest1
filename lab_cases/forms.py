# DENTALCLINICSYSTEM/lab_cases/forms.py

from django import forms
from django.utils import timezone
from .models import DentalLab, LabCase, LabPayment
from patients.models import Patient
from staff.models import StaffMember
from decimal import Decimal
from phonenumber_field.phonenumber import to_python, PhoneNumber
from phonenumbers.data import _COUNTRY_CODE_TO_REGION_CODE
from babel import Locale
from django.core.exceptions import ValidationError

from billing.models import Supplier

def get_country_choices():
    english_locale = Locale.parse("en")
    choices = [('', '---------')]
    processed_codes = set()
    for code, region_codes in sorted(_COUNTRY_CODE_TO_REGION_CODE.items()):
        primary_region = region_codes[0]
        if primary_region in processed_codes:
            continue
        try:
            country_name = english_locale.territories.get(primary_region, primary_region)
            choices.append((str(code), f"{country_name} (+{code})"))
        except Exception:
            choices.append((str(code), f"{primary_region} (+{code})"))
        processed_codes.add(primary_region)
    return sorted(choices, key=lambda x: x[1])

class DentalLabForm(forms.ModelForm):
    country_code = forms.ChoiceField(
        label="Country Code",
        choices=get_country_choices(),
        initial='91',
        required=True
    )
    national_number = forms.CharField(
        label="Phone Number",
        required=False, # This is key: it's optional, but if present, must be valid
        widget=forms.TextInput(attrs={'placeholder': 'e.g., 9876543210'})
    )

    class Meta:
        model = DentalLab
        fields = [
            'name', 'contact_person', 'country_code', 'national_number', 'email',
            'address', 'notes', 'is_active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Name of the Dental Lab'}),
            'contact_person': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., John Doe'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'e.g., contact@labname.com'}),
            'address': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 4, 'class': 'form-control', 'placeholder': 'Notes about specialties, turnaround times, etc.'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.contact_number:
            if isinstance(self.instance.contact_number, PhoneNumber):
                self.fields['country_code'].initial = str(self.instance.contact_number.country_code)
                self.fields['national_number'].initial = str(self.instance.contact_number.national_number)
            else:
                phone = str(self.instance.contact_number)
                if phone.startswith('+') and len(phone) > 3:
                    for code, _ in get_country_choices():
                        if code and phone.startswith('+' + code):
                            self.fields['country_code'].initial = code
                            self.fields['national_number'].initial = phone[len(code)+1:]
                            break
        # Ensure all fields have 'form-control' class
        for field_name, field in self.fields.items():
            if 'class' not in field.widget.attrs:
                current_classes = field.widget.attrs.get('class', '')
                if 'form-control' not in current_classes:
                    field.widget.attrs['class'] = (current_classes + ' form-control').strip()
            # Special handling for select2 if needed, though forms.py already has it for some fields
            if 'select2-enable' in field.widget.attrs.get('class', ''):
                field.widget.attrs['class'] += ' select2-enable' # Ensure select2 is enabled

    def clean(self):
        cleaned_data = super().clean()
        country_code = cleaned_data.get("country_code")
        national_number = cleaned_data.get("national_number")
        email = cleaned_data.get("email")

        # --- Phone Number Validation and Cross-Check ---
        if national_number and country_code and country_code != '': # Check if both parts of phone are provided
            try:
                phone_number = to_python(f"+{country_code}{national_number}")
                # The phonenumber_field's to_python will return None if parsing fails
                if not (phone_number and phone_number.is_valid()):
                    self.add_error('national_number', "The phone number is not valid for the selected country.")
            except Exception: # Catch any parsing errors
                self.add_error('national_number', "Invalid phone number format.")
            
            if not self.errors.get('national_number'):
                # Check against DentalLab itself
                dental_lab_qs = DentalLab.objects.filter(contact_number=phone_number).exclude(pk=self.instance.pk)
                if dental_lab_qs.exists():
                    self.add_error('national_number', f"This phone number is already in use by dental lab: {dental_lab_qs.first().name}.")

                # Check against Staff
                staff = StaffMember.objects.filter(contact_number=phone_number).first()
                if staff:
                    self.add_error('national_number', f"This phone number is already in use by staff: {staff.user.get_full_name() or staff.user.username}.")

                # Check against Patients
                patient = Patient.objects.filter(contact_number=phone_number).first()
                if patient:
                    self.add_error('national_number', f"This phone number is already in use by patient: {patient.name}.")
                
                # Check against Suppliers (from billing app)
                supplier = Supplier.objects.filter(phone_number=phone_number).first()
                if supplier:
                    self.add_error('national_number', f"This phone number is already in use by supplier: {supplier.name}.")

                cleaned_data['contact_number'] = phone_number
        elif national_number and (not country_code or country_code == ''):
            self.add_error('country_code', "Please select a country code for the phone number.")
        elif country_code and country_code != '' and not national_number:
            self.add_error('national_number', "Please enter a national number for the selected country code.")
        else: # Both are empty or not provided
            cleaned_data['contact_number'] = None

        # --- Email Uniqueness and Cross-Check ---
        if email:
            # Check within DentalLab itself
            dental_lab_email_qs = DentalLab.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
            if dental_lab_email_qs.exists():
                self.add_error('email', f"This email address is already in use by dental lab: {dental_lab_email_qs.first().name}.")

            # Cross-check with StaffMember
            staff = StaffMember.objects.filter(user__email__iexact=email).first()
            if staff:
                name = f"{staff.user.first_name} {staff.user.last_name}".strip() or staff.user.username
                self.add_error('email', f"This email address is already in use by staff: {name}.")

            # Cross-check with Supplier
            supplier = Supplier.objects.filter(email__iexact=email).first()
            if supplier:
                self.add_error('email', f"This email address is already in use by supplier: {supplier.name}.")

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if 'contact_number' in self.cleaned_data:
            instance.contact_number = self.cleaned_data['contact_number']
        if commit:
            instance.save()
        return instance

class LabCaseFilterForm(forms.Form):
    status = forms.ChoiceField(choices=[('', 'All Statuses')] + LabCase.CASE_STATUS_CHOICES, required=False, widget=forms.Select(attrs={'class': 'form-control'}))
    lab = forms.ModelChoiceField(
        queryset=DentalLab.objects.none(),
        required=False,
        empty_label="All Labs",
        widget=forms.Select(attrs={'class': 'form-control select2-enable'})
    )
    start_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}))
    end_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['lab'].queryset = DentalLab.objects.all()

class LabCaseForm(forms.ModelForm):
    patient = forms.ModelChoiceField(
        queryset=Patient.objects.all().order_by('name'),
        widget=forms.Select(attrs={'class': 'form-control select2-enable'})
    )
    doctor = forms.ModelChoiceField(
        queryset=StaffMember.objects.filter(user__groups__name='Doctors', is_active=True).select_related('user').order_by('user__first_name', 'user__last_name'),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control select2-enable'})
    )
    lab = forms.ModelChoiceField(
        queryset=DentalLab.objects.filter(is_active=True).order_by('name'),
        label="Dental Lab",
        widget=forms.Select(attrs={'class': 'form-control select2-enable'})
    )

    class Meta:
        model = LabCase
        fields = [
            'patient', 'doctor', 'lab', 'case_type', 'description', 'status',
            'cost_per_unit', 'units', 'gst_percentage', 'date_sent', 'date_due', 'date_received'
        ]
        labels = {
            'cost_per_unit': 'Cost per Unit',
            'gst_percentage': 'GST %',
        }
        widgets = {
            'case_type': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Zirconia Crown, PFM Bridge'}),
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control', 'placeholder': 'Detailed instructions for the lab...'}),
            'status': forms.Select(attrs={'class': 'form-control', 'id': 'id_status'}),
            'cost_per_unit': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
            'units': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'gst_percentage': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
            'date_sent': forms.DateInput(attrs={'type': 'date', 'class': 'form-control', 'id': 'id_date_sent'}),
            'date_due': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'date_received': forms.DateInput(attrs={'type': 'date', 'class': 'form-control', 'id': 'id_date_received'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get("status")
        date_sent = cleaned_data.get("date_sent")
        date_due = cleaned_data.get("date_due")
        date_received = cleaned_data.get("date_received")
        
        # --- The Definitive Validation Logic ---

        # 1. A case cannot be due before it is sent.
        if date_sent and date_due and date_due < date_sent:
            self.add_error('date_due', "The due date cannot be before the date the case was sent.")

        # 2. A case cannot be received before it is sent.
        if date_sent and date_received and date_received < date_sent:
            self.add_error('date_received', "The date received cannot be before the date the case was sent.")

        # 3. Status-based rules
        if status == 'CREATED':
            if date_sent:
                self.add_error('date_sent', "A 'Created' case cannot have a 'Date Sent'. Please clear the date or change the status.")
            if date_received:
                self.add_error('date_received', "A 'Created' case cannot have a 'Date Received'. Please clear the date or change the status.")
        elif status == 'SENT':
            if not date_sent:
                self.add_error('date_sent', "'Date Sent' is required for a 'Sent to Lab' case.")
            if date_received:
                self.add_error('date_received', "A 'Sent' case cannot have a 'Date Received'. Please clear the date or change the status to 'Received'.")
        elif status in ['RECEIVED', 'COMPLETED']:
            if not date_sent:
                self.add_error('date_sent', "'Date Sent' is required for this status.")
            if not date_received:
                self.add_error('date_received', "'Date Received' is required for this status.")

        return cleaned_data

class LabPaymentForm(forms.ModelForm):
    payment_date = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        initial=timezone.now
    )
    class Meta:
        model = LabPayment
        fields = ['payment_date', 'amount', 'payment_method', 'notes']

    def __init__(self, *args, **kwargs):
        self.lab_case = kwargs.pop('lab_case', None)
        super().__init__(*args, **kwargs)

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if self.lab_case and amount > self.lab_case.balance_due:
            raise forms.ValidationError(f"Payment cannot exceed the balance due of ₹{self.lab_case.balance_due:.2f}")
        return amount