# DENTALCLINICSYSTEM/patients/forms.py

from django import forms
from django.core.exceptions import ValidationError
from .models import Patient
from staff.models import StaffMember # Imported for cross-check
from billing.models import Supplier # Imported for cross-check
from lab_cases.models import DentalLab # Imported for cross-check
from phonenumber_field.phonenumber import to_python, PhoneNumber
from phonenumbers.data import _COUNTRY_CODE_TO_REGION_CODE
from babel import Locale
import re

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
            processed_codes.add(primary_region)
        except Exception:
            choices.append((str(code), f"{primary_region} (+{code})"))
            processed_codes.add(primary_region)
    return sorted(choices, key=lambda x: x[1])

class PatientForm(forms.ModelForm):
    country_code = forms.ChoiceField(
        label="Country Code",
        choices=get_country_choices,
        initial='91',
        required=True
    )
    national_number = forms.CharField(
        label="Phone Number",
        required=True, # Phone number is required for patients
        widget=forms.TextInput(attrs={'placeholder': 'e.g., 9876543210'})
    )
    date_of_birth = forms.DateField(
        label="Date of Birth",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    pincode = forms.CharField(
        label="Pincode / ZIP Code",
        required=False  # Make pincode optional in the form
    )

    class Meta:
        model = Patient
        fields = [
            'name',
            'date_of_birth',
            'gender',
            'place',
            'pincode',
            'allergies',
            'ongoing_conditions',
            'medications'
        ]
        exclude = ['contact_number'] # Exclude the model field, as we handle it via two form fields

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance or not self.instance.pk:
            self.fields['place'].initial = ''
            self.fields['pincode'].initial = ''
        
        # Populate country_code and national_number from existing instance
        if self.instance and self.instance.pk and self.instance.contact_number:
            if isinstance(self.instance.contact_number, PhoneNumber):
                self.fields['country_code'].initial = str(self.instance.contact_number.country_code)
                self.fields['national_number'].initial = str(self.instance.contact_number.national_number)
            else: # Fallback for existing data that might not be PhoneNumber objects yet
                phone = str(self.instance.contact_number)
                if phone.startswith('+') and len(phone) > 3:
                    for code, _ in get_country_choices():
                        if code and phone.startswith('+' + code):
                            self.fields['country_code'].initial = code
                            self.fields['national_number'].initial = phone[len(code)+1:]
                            break
        
        # Apply form-control class to all widgets
        for field in self.fields.values():
            if 'class' not in field.widget.attrs:
                field.widget.attrs.update({'class': 'form-control'})

    def clean(self):
        cleaned_data = super().clean()
        country_code = cleaned_data.get("country_code")
        national_number = cleaned_data.get("national_number")
        
        # --- Phone Number Validation and Cross-Check ---
        if national_number and country_code and country_code != '':
            try:
                phone_number = to_python(f"+{country_code}{national_number}")
                if not (phone_number and phone_number.is_valid()):
                    self.add_error('national_number', "The phone number is not valid for the selected country.")
            except Exception:
                self.add_error('national_number', "Invalid phone number format.")

            # Only proceed with uniqueness checks if the phone number format is valid
            if not self.errors.get('national_number'):
                # Check Patient (excluding self)
                patient_qs = Patient.objects.filter(contact_number=phone_number).exclude(pk=self.instance.pk)
                if patient_qs.exists():
                    patient = patient_qs.first()
                    self.add_error('national_number', f"This phone number is already in use by patient: {patient.name}.")
                
                # Check StaffMember
                staff = StaffMember.objects.filter(contact_number=phone_number).first()
                if staff:
                    name = staff.name
                    self.add_error('national_number', f"This phone number is already in use by staff: {name}.")
                
                # Check Supplier
                supplier = Supplier.objects.filter(phone_number=phone_number).first()
                if supplier:
                    self.add_error('national_number', f"This phone number is already in use by supplier: {supplier.name}.")

                # Check DentalLab
                dental_lab = DentalLab.objects.filter(contact_number=phone_number).first()
                if dental_lab:
                    self.add_error('national_number', f"This phone number is already in use by dental lab: {dental_lab.name}.")

                cleaned_data['contact_number'] = phone_number # Store the validated PhoneNumber object
        elif national_number and (not country_code or country_code == ''):
            self.add_error('country_code', "Please select a country code for the phone number.")
        elif country_code and country_code != '' and not national_number:
            self.add_error('national_number', "Please enter a national number for the selected country code.")
        else: # Both are empty or not provided
            cleaned_data['contact_number'] = None # Ensure contact_number is None if both are empty

        pincode = cleaned_data.get("pincode")
        if pincode:  # Only validate if present
            validation_pattern = None
            error_message = ""

            if country_code == '91':
                validation_pattern = r'^\d{6}$'
                error_message = "Enter a valid 6-digit Indian PIN code."
            elif country_code == '1':
                validation_pattern = r'^\d{5}(?:[-\s]\d{4})?$'
                error_message = "Enter a valid 5-digit US ZIP code."
            
            if validation_pattern and not re.match(validation_pattern, pincode):
                self.add_error("pincode", error_message) # Use add_error for consistency

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        # The clean method already sets cleaned_data['contact_number']
        if 'contact_number' in self.cleaned_data:
            instance.contact_number = self.cleaned_data['contact_number']
        if commit:
            instance.save()
        return instance