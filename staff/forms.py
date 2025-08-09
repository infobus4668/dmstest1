# DENTALCLINICSYSTEM/staff/forms.py

from django import forms
from django.contrib.auth.models import User, Group
from django.db import transaction
from .models import StaffMember
from patients.models import Patient # Keep for phone cross-check ONLY
from billing.models import Supplier # Keep for phone and email cross-check
from lab_cases.models import DentalLab # Keep for phone and email cross-check
from phonenumber_field.phonenumber import to_python, PhoneNumber
from phonenumbers.phonenumberutil import is_valid_number
from phonenumbers.data import _COUNTRY_CODE_TO_REGION_CODE # This import is essential for get_country_choices
from babel import Locale

def get_country_choices():
    """Generates a list of countries with their calling codes."""
    english_locale = Locale.parse("en")
    choices = [('', '---------')]
    processed_codes = set()
    for code, region_codes in sorted(_COUNTRY_CODE_TO_REGION_CODE.items()):
        primary_region = region_codes[0]
        if primary_region in processed_codes: continue
        try:
            country_name = english_locale.territories.get(primary_region, primary_region)
            choices.append((str(code), f"{country_name} (+{code})"))
            processed_codes.add(primary_region)
        except Exception:
            choices.append((str(code), f"{primary_region} (+{code})"))
            processed_codes.add(primary_region)
    return sorted(choices, key=lambda x: x[1])

class StaffMemberForm(forms.ModelForm):
    first_name = forms.CharField(max_length=100, required=True)
    last_name = forms.CharField(max_length=100, required=True)
    email = forms.EmailField(required=True)
    username = forms.CharField(max_length=150, required=True)
    password = forms.CharField(widget=forms.PasswordInput, required=False, help_text="Leave blank to keep the current password.")
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all().order_by('name'),
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label="Roles",
        error_messages={'required': 'You must assign at least one role.'}
    )
    country_code = forms.ChoiceField(choices=get_country_choices, required=False, label="Country Code", initial='91')
    national_number = forms.CharField(label="Phone Number", required=False)

    class Meta:
        model = StaffMember
        fields = [
            'address', 'date_of_birth', 'is_active',
            'specialization', 'credentials'
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'credentials': forms.Textarea(attrs={'rows': 3, 'placeholder': 'e.g., M.D.S., F.A.C.D.'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['username'].initial = self.instance.user.username
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email
            self.fields['groups'].initial = self.instance.user.groups.all()
            self.fields['username'].disabled = True
            
            if self.instance.contact_number and isinstance(self.instance.contact_number, PhoneNumber):
                self.fields['country_code'].initial = str(self.instance.contact_number.country_code)
                self.fields['national_number'].initial = str(self.instance.contact_number.national_number)
        else:
            self.fields['password'].required = True
            self.fields['password'].help_text = "The password is required for new staff members."

    def clean_username(self):
        username = self.cleaned_data['username']
        if not self.instance.pk and User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("A user with this username already exists.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            # Staff (User) email uniqueness
            qs = User.objects.filter(email__iexact=email)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.user.pk)
            if qs.exists():
                user = qs.first()
                name = f"{user.first_name} {user.last_name}".strip() or user.username
                raise forms.ValidationError(f"This email address is already in use by staff: {name}.")

            # Cross-model uniqueness check: Supplier
            supplier = Supplier.objects.filter(email__iexact=email).first()
            if supplier:
                raise forms.ValidationError(f"This email address is already in use by supplier: {supplier.name}.")

            # Cross-model uniqueness check: DentalLab
            from lab_cases.models import DentalLab
            dental_lab = DentalLab.objects.filter(email__iexact=email).first()
            if dental_lab:
                raise forms.ValidationError(f"This email address is already in use by dental lab: {dental_lab.name}.")

        return email

    def clean(self):
        cleaned_data = super().clean()
        country_code = cleaned_data.get("country_code")
        national_number = cleaned_data.get("national_number")

        if country_code and national_number:
            try:
                phone_number = to_python(f"+{country_code}{national_number}")
                if not (phone_number and phone_number.is_valid()): # Changed condition and message
                    self.add_error('national_number', "The phone number is not valid for the selected country.")
                else:
                    # Check StaffMember (excluding self)
                    staff_qs = StaffMember.objects.filter(contact_number=phone_number).exclude(pk=self.instance.pk)
                    if staff_qs.exists():
                        staff = staff_qs.first()
                        name = staff.name
                        self.add_error('national_number', f"This phone number is already in use by staff: {name}.")
                    else:
                        # Check Patient
                        patient = Patient.objects.filter(contact_number=phone_number).first()
                        if patient:
                            self.add_error('national_number', f"This phone number is already in use by patient: {patient.name}.")
                        else:
                            # Check Supplier
                            supplier = Supplier.objects.filter(phone_number=phone_number).first()
                            if supplier:
                                self.add_error('national_number', f"This phone number is already in use by supplier: {supplier.name}.")
                            else:
                                # Check DentalLab
                                dental_lab = DentalLab.objects.filter(contact_number=phone_number).first()
                                if dental_lab:
                                    self.add_error('national_number', f"This phone number is already in use by dental lab: {dental_lab.name}.")
                                else:
                                    cleaned_data['contact_number'] = phone_number
            except Exception:
                self.add_error('national_number', "Invalid phone number format.")
        elif country_code or national_number:
            self.add_error('national_number', "Both country code and phone number are required.")
        else:
            cleaned_data['contact_number'] = None
        
        groups = cleaned_data.get('groups')
        if groups and groups.filter(name='Doctors').exists():
            if not cleaned_data.get('specialization'):
                self.add_error('specialization', 'Specialization is required for users with the "Doctors" role.')
                
        return cleaned_data

    @transaction.atomic
    def save(self, commit=True):
        if self.instance.pk:
            user = self.instance.user
        else:
            user = User()
            user.username = self.cleaned_data['username']

        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']
        user.is_staff = True
        if self.cleaned_data.get('password'):
            user.set_password(self.cleaned_data['password'])
        user.save()
        user.groups.set(self.cleaned_data['groups'])
        
        self.instance.user = user
        staff_member = super().save(commit=False)
        staff_member.contact_number = self.cleaned_data.get('contact_number')
        
        if commit:
            staff_member.save()
            
        return staff_member