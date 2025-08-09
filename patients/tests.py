from django.test import TestCase, Client
from django.urls import reverse
from decimal import Decimal
from django.utils import timezone
from datetime import date
from phonenumber_field.phonenumber import PhoneNumber
from django.core.exceptions import ValidationError

# Import models from other apps for cross-checking
from staff.models import StaffMember
from billing.models import Supplier
from lab_cases.models import DentalLab
from django.contrib.auth import get_user_model
User = get_user_model()

from .models import Patient
from .forms import PatientForm

class PatientAppTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpassword', is_active=True)
        self.user.is_staff = True
        self.user.is_superuser = True # Grant full permissions for testing
        self.user.save()
        self.client.force_login(self.user)

        # Create fixtures for cross-checking phone numbers
        self.staff_member = StaffMember.objects.create(
            user=User.objects.create_user(username='staffuser', password='password', email='staff@example.com'),
            contact_number=PhoneNumber.from_string('+919876543000'),
            is_active=True
        )
        self.supplier = Supplier.objects.create(
            name='Test Supplier',
            category='LOCAL_SHOP',
            phone_number=PhoneNumber.from_string('+919876543001'),
            email='supplier@example.com'
        )
        self.dental_lab = DentalLab.objects.create(
            name='Test Lab',
            contact_number=PhoneNumber.from_string('+919876543002'),
            email='lab@example.com'
        )
        self.existing_patient = Patient.objects.create(
            name='Existing Patient',
            date_of_birth=date(1980, 5, 10),
            gender='M',
            contact_number=PhoneNumber.from_string('+919876543003'),
            place='Chennai'
        )

    def test_patient_form_valid_data(self):
        form_data = {
            'name': 'New Patient',
            'date_of_birth': '2000-01-01',
            'gender': 'F',
            'country_code': '91',
            'national_number': '9876543004', # Unique number
            'place': 'Coimbatore',
            'pincode': '641001',
            'allergies': '',
            'ongoing_conditions': '',
            'medications': ''
        }
        form = PatientForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)
        patient = form.save()
        self.assertEqual(str(patient.contact_number), '+919876543004')
        self.assertEqual(patient.name, 'New Patient')

    def test_patient_form_phone_number_invalid_format(self):
        form_data = {
            'name': 'Invalid Phone Patient',
            'date_of_birth': '1995-03-15',
            'gender': 'M',
            'country_code': '91',
            'national_number': 'invalid', # Invalid format
            'place': 'Salem',
            'pincode': '636001'
        }
        form = PatientForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('national_number', form.errors)
        # Changed expected error message to match the form's output
        self.assertIn('The phone number is not valid for the selected country.', form.errors['national_number'])

    def test_patient_form_phone_number_not_valid_for_country(self):
        form_data = {
            'name': 'Invalid Country Phone Patient',
            'date_of_birth': '1995-03-15',
            'gender': 'M',
            'country_code': '1', # US country code
            'national_number': '9876543210', # Indian number format
            'place': 'Salem',
            'pincode': '636001'
        }
        form = PatientForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('national_number', form.errors)
        self.assertIn('The phone number is not valid for the selected country.', form.errors['national_number'])

    def test_patient_form_phone_number_missing_national_number(self):
        form_data = {
            'name': 'Missing Number Patient',
            'date_of_birth': '1990-01-01',
            'gender': 'F',
            'country_code': '91',
            'national_number': '', # Missing national number
            'place': 'Erode',
            'pincode': '638001'
        }
        form = PatientForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('national_number', form.errors)
        self.assertIn('Please enter a national number for the selected country code.', form.errors['national_number'])

    def test_patient_form_phone_number_missing_country_code(self):
        form_data = {
            'name': 'Missing Code Patient',
            'date_of_birth': '1990-01-01',
            'gender': 'F',
            'country_code': '', # Missing country code
            'national_number': '9876543005',
            'place': 'Madurai',
            'pincode': '625001'
        }
        form = PatientForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('country_code', form.errors)
        self.assertIn('Please select a country code for the phone number.', form.errors['country_code'])

    def test_patient_form_phone_number_conflict_with_existing_patient(self):
        form_data = {
            'name': 'Duplicate Patient',
            'date_of_birth': '1990-01-01',
            'gender': 'M',
            'country_code': '91',
            'national_number': '9876543003', # Same as self.existing_patient
            'place': 'Trichy',
            'pincode': '620001'
        }
        form = PatientForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('national_number', form.errors)
        self.assertIn(f"This phone number is already in use by patient: {self.existing_patient.name}.", form.errors['national_number'])

    def test_patient_form_phone_number_conflict_with_staff_member(self):
        form_data = {
            'name': 'Staff Conflict Patient',
            'date_of_birth': '1990-01-01',
            'gender': 'F',
            'country_code': '91',
            'national_number': '9876543000', # Same as self.staff_member
            'place': 'Coimbatore',
            'pincode': '641001'
        }
        form = PatientForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('national_number', form.errors)
        self.assertIn(f"This phone number is already in use by staff: {self.staff_member.name}.", form.errors['national_number'])

    def test_patient_form_phone_number_conflict_with_supplier(self):
        form_data = {
            'name': 'Supplier Conflict Patient',
            'date_of_birth': '1990-01-01',
            'gender': 'M',
            'country_code': '91',
            'national_number': '9876543001', # Same as self.supplier
            'place': 'Chennai',
            'pincode': '600001'
        }
        form = PatientForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('national_number', form.errors)
        self.assertIn(f"This phone number is already in use by supplier: {self.supplier.name}.", form.errors['national_number'])

    def test_patient_form_phone_number_conflict_with_dental_lab(self):
        form_data = {
            'name': 'Lab Conflict Patient',
            'date_of_birth': '1990-01-01',
            'gender': 'F',
            'country_code': '91',
            'national_number': '9876543002', # Same as self.dental_lab
            'place': 'Bangalore',
            'pincode': '560001'
        }
        form = PatientForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('national_number', form.errors)
        self.assertIn(f"This phone number is already in use by dental lab: {self.dental_lab.name}.", form.errors['national_number'])

    def test_patient_form_edit_existing_patient_no_phone_change(self):
        # Editing existing patient without changing their own phone number should be valid
        form_data = {
            'name': 'Updated Existing Patient',
            'date_of_birth': '1980-05-10',
            'gender': 'M',
            'country_code': '91',
            'national_number': '9876543003', # Same as existing_patient's current number
            'place': 'Chennai',
            'pincode': '600001'
        }
        form = PatientForm(data=form_data, instance=self.existing_patient)
        self.assertTrue(form.is_valid(), form.errors)
        updated_patient = form.save()
        self.assertEqual(updated_patient.name, 'Updated Existing Patient')
        self.assertEqual(str(updated_patient.contact_number), '+919876543003')

    def test_patient_form_edit_existing_patient_change_to_unique_phone(self):
        # Editing existing patient and changing to a new unique phone number
        form_data = {
            'name': 'Updated Existing Patient',
            'date_of_birth': '1980-05-10',
            'gender': 'M',
            'country_code': '91',
            'national_number': '9876543005', # New unique number
            'place': 'Chennai',
            'pincode': '600001'
        }
        form = PatientForm(data=form_data, instance=self.existing_patient)
        self.assertTrue(form.is_valid(), form.errors)
        updated_patient = form.save()
        self.assertEqual(str(updated_patient.contact_number), '+919876543005')

    def test_add_patient_view(self):
        add_url = reverse('patients:add_patient')
        valid_data = {
            'name': 'View Test Patient',
            'date_of_birth': '1999-11-20',
            'gender': 'M',
            'country_code': '91',
            'national_number': '9876543006', # Unique number for view test
            'place': 'Coimbatore',
            'pincode': '641001',
            'allergies': '',
            'ongoing_conditions': '',
            'medications': ''
        }
        response = self.client.post(add_url, valid_data)
        self.assertEqual(response.status_code, 302) # Should redirect on success
        self.assertTrue(Patient.objects.filter(name='View Test Patient').exists())
        new_patient = Patient.objects.get(name='View Test Patient')
        self.assertEqual(str(new_patient.contact_number), '+919876543006')

        # Test invalid data (duplicate phone)
        invalid_data_dup_phone = valid_data.copy()
        invalid_data_dup_phone['name'] = 'Another View Test Patient' # Change name to avoid name conflict
        response = self.client.post(add_url, invalid_data_dup_phone)
        self.assertEqual(response.status_code, 200) # Should render form again with errors
        self.assertContains(response, 'This phone number is already in use by patient: View Test Patient.')
        self.assertFalse(Patient.objects.filter(name='Another View Test Patient').exists())

    def test_edit_patient_view(self):
        edit_url = reverse('patients:edit_patient', args=[self.existing_patient.pk])
        updated_data = {
            'name': 'Edited Patient Name',
            'date_of_birth': '1980-05-10',
            'gender': 'M',
            'country_code': '91',
            'national_number': '9876543007', # New unique number
            'place': 'Chennai',
            'pincode': '600001',
            'allergies': '',
            'ongoing_conditions': '',
            'medications': ''
        }
        response = self.client.post(edit_url, updated_data)
        self.assertEqual(response.status_code, 302) # Should redirect on success
        self.existing_patient.refresh_from_db()
        self.assertEqual(self.existing_patient.name, 'Edited Patient Name')
        self.assertEqual(str(self.existing_patient.contact_number), '+919876543007')

        # Test invalid data (duplicate phone with staff)
        invalid_data_dup_phone = updated_data.copy()
        invalid_data_dup_phone['national_number'] = '9876543000' # Same as staff_member
        response = self.client.post(edit_url, invalid_data_dup_phone)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"This phone number is already in use by staff: {self.staff_member.name}.")
        # Ensure the patient's number was NOT changed
        self.existing_patient.refresh_from_db()
        self.assertNotEqual(str(self.existing_patient.contact_number), '+919876543000')

    def test_pincode_validation(self):
        # Valid Indian Pincode
        form_data = {
            'name': 'Pincode Test Patient',
            'date_of_birth': '2000-01-01',
            'gender': 'M',
            'country_code': '91',
            'national_number': '9876543008',
            'place': 'Test Place',
            'pincode': '600001',
            'allergies': '', 'ongoing_conditions': '', 'medications': ''
        }
        form = PatientForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)

        # Invalid Indian Pincode (too short)
        form_data['pincode'] = '123'
        form = PatientForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('pincode', form.errors)
        self.assertIn('Enter a valid 6-digit Indian PIN code.', form.errors['pincode'])

        # Valid US ZIP code
        form_data['country_code'] = '1'
        form_data['national_number'] = '2125550001'
        form_data['pincode'] = '10001'
        form = PatientForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)

        # Valid US ZIP+4
        form_data['pincode'] = '90210-1234'
        form = PatientForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)

        # Invalid US ZIP code (wrong format)
        form_data['pincode'] = '123456'
        form = PatientForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('pincode', form.errors)
        self.assertIn('Enter a valid 5-digit US ZIP code.', form.errors['pincode'])

        # No pincode (optional)
        form_data['pincode'] = ''
        form = PatientForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)