from django.test import TestCase, Client
from django.urls import reverse
from decimal import Decimal
from django.utils import timezone
from datetime import date
from phonenumber_field.phonenumber import PhoneNumber
from django.core.exceptions import ValidationError


from lab_cases.models import DentalLab, LabCase, LabPayment
from lab_cases.forms import LabCaseForm, LabPaymentForm, LabCaseFilterForm, DentalLabForm
from patients.models import Patient
from staff.models import StaffMember
from django.contrib.auth import get_user_model
User = get_user_model()
from appointments.models import Appointment
from billing.models import Supplier


class LabCasesTestSuite(TestCase):

    def setUp(self):
        # Create user and grant all permissions for testing
        self.user = User.objects.create_user(username='doc', password='test', is_active=True)
        self.user.first_name = "John"
        self.user.last_name = "Smith"
        self.user.email = "doc@example.com"
        self.user.is_staff = True
        self.user.is_superuser = True
        self.user.save()

        # Create StaffMember (using PhoneNumberField directly)
        self.doctor = StaffMember.objects.create(user=self.user, is_active=True, contact_number=PhoneNumber.from_string('+919876543210'))
        StaffMember.objects.create(user=User.objects.create_user(username='staff2', password='test', email='staff2@example.com'), is_active=True, contact_number=PhoneNumber.from_string('+919999988888'))
        
        # Create Patient (using PhoneNumberField directly)
        self.patient = Patient.objects.create(
            name='John Doe',
            date_of_birth=date(1990, 1, 1),
            contact_number=PhoneNumber.from_string('+919876543211'),
        )
        Patient.objects.create(name='Jane Doe', date_of_birth=date(1991,1,1), contact_number=PhoneNumber.from_string('+919999977777'))

        # Create Supplier (using PhoneNumberField directly)
        self.supplier = Supplier.objects.create(
            name='Test Supplier',
            phone_number=PhoneNumber.from_string('+919876543212'),
            email='supplier@example.com' 
        )
        
        self.lab = DentalLab.objects.create(name='Bright Lab', contact_number=PhoneNumber.from_string('+919876543213'), email='brightlab@example.com')
        self.client = Client()
        self.client.force_login(self.user)
        self.case_data = {
            'patient': self.patient,
            'doctor': self.doctor,
            'lab': self.lab,
            'case_type': 'Zirconia Crown',
            'description': 'Upper right 6, A2',
            'cost_per_unit': Decimal('1000'),
            'units': 2,
            'gst_percentage': Decimal('5.00')
        }

    def test_lab_case_crud(self):
        lab_case = LabCase.objects.create(**self.case_data)
        self.assertEqual(lab_case.total_cost, Decimal('2100'))
        lab_case.units = 3
        lab_case.save()
        self.assertEqual(lab_case.total_cost, Decimal('3150'))
        pk = lab_case.pk
        lab_case.delete()
        self.assertFalse(LabCase.objects.filter(pk=pk).exists())

    def test_dental_lab_crud(self):
        lab = DentalLab.objects.create(name="Test Lab 2", contact_number=PhoneNumber.from_string('+919876543214'), email='testlab2@example.com')
        lab.contact_person = "Anna"
        lab.save()
        pk = lab.pk
        lab.delete()
        self.assertFalse(DentalLab.objects.filter(pk=pk).exists())

    def test_lab_payment_overpayment_model_and_form(self):
        lab_case = LabCase.objects.create(**self.case_data)
        LabPayment.objects.create(
            lab_case=lab_case,
            amount=lab_case.total_cost,
            payment_method='BANK'
        )
        with self.assertRaises(ValidationError):
            LabPayment.objects.create(
                lab_case=lab_case,
                amount=Decimal('1.00'),
                payment_method='BANK'
            )
        form = LabPaymentForm(data={
            'payment_date': timezone.now(),
            'amount': lab_case.total_cost + Decimal('1.00'),
            'payment_method': 'BANK'
        }, lab_case=lab_case)
        self.assertFalse(form.is_valid())
        self.assertIn('amount', form.errors)

    def test_lab_case_creation_from_appointment(self):
        appointment = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            appointment_datetime=timezone.now()
        )
        url = reverse('lab_cases:add_lab_case_from_appointment', args=[appointment.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)
        data = self.case_data.copy()
        data.update({'status': 'CREATED'})
        response = self.client.post(url, data)
        self.assertIn(response.status_code, [302, 200])

    def test_lab_case_filter_form_queryset_dynamic(self):
        form = LabCaseFilterForm()
        self.assertIn(self.lab, form.fields['lab'].queryset)
        DentalLab.objects.create(name="Fresh Lab", contact_number=PhoneNumber.from_string('+919876543215'), email='freshlab@example.com')
        form = LabCaseFilterForm()
        self.assertTrue(DentalLab.objects.filter(name="Fresh Lab").exists())
        self.assertIn("Fresh Lab", [l.name for l in form.fields['lab'].queryset])

    def test_lab_case_form_validation_logic(self):
        form = LabCaseForm(data={
            **self.case_data,
            'status': 'SENT',
            'date_sent': '2024-06-10',
            'date_due': '2024-06-01'
        })
        self.assertFalse(form.is_valid())
        self.assertIn('date_due', form.errors)
        form = LabCaseForm(data={
            **self.case_data,
            'status': 'RECEIVED',
            'date_sent': '2024-06-10',
            'date_received': '2024-06-01'
        })
        self.assertFalse(form.is_valid())
        self.assertIn('date_received', form.errors)

    def test_admin_calculated_fields(self):
        lab_case = LabCase.objects.create(**self.case_data)
        LabPayment.objects.create(
            lab_case=lab_case,
            amount=Decimal('500'),
            payment_method='BANK'
        )
        self.assertEqual(lab_case.amount_paid, Decimal('500'))
        self.assertEqual(lab_case.balance_due, lab_case.total_cost - Decimal('500'))

    def test_lab_list_view(self):
        url = reverse('lab_cases:lab_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.lab.name)

    def test_lab_case_list_and_filter_view(self):
        LabCase.objects.create(**self.case_data)
        url = reverse('lab_cases:lab_case_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Lab Cases')

    def test_lab_case_detail_view(self):
        lab_case = LabCase.objects.create(**self.case_data)
        url = reverse('lab_cases:lab_case_detail', args=[lab_case.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, lab_case.case_type)

    # New tests for DentalLabForm phone validation and cross-checking
    def test_dental_lab_form_phone_number_validation(self):
        # Valid phone number - ENSURE THIS IS UNIQUE AND DOES NOT CLASH WITH OTHER FIXTURES
        form_data = {
            'name': 'New Valid Lab',
            'contact_person': 'Test Contact',
            'country_code': '91',
            'national_number': '9876540000', # Changed to a unique number that shouldn't clash
            'email': 'newvalid@example.com',
            'address': '123 Test St',
            'notes': '',
            'is_active': True
        }
        form = DentalLabForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)
        instance = form.save(commit=False)
        self.assertEqual(str(instance.contact_number), '+919876540000')

        # Invalid national number format
        form_data_invalid_num = {
            'name': 'Invalid Num Lab',
            'contact_person': 'Test Contact',
            'country_code': '91',
            'national_number': 'abc',
            'email': 'invalidnum@example.com',
            'address': '123 Test St',
            'notes': '',
            'is_active': True
        }
        form = DentalLabForm(data=form_data_invalid_num)
        self.assertFalse(form.is_valid())
        self.assertIn('national_number', form.errors)

        # Missing national number but country code present
        form_data_missing_num = {
            'name': 'Missing Num Lab',
            'contact_person': 'Test Contact',
            'country_code': '91',
            'national_number': '',
            'email': 'missingnum@example.com',
            'address': '123 Test St',
            'notes': '',
            'is_active': True
        }
        form = DentalLabForm(data=form_data_missing_num)
        self.assertFalse(form.is_valid())
        self.assertIn('national_number', form.errors)

        # Missing country code but national number present
        form_data_missing_code = {
            'name': 'Missing Code Lab',
            'contact_person': 'Test Contact',
            'country_code': '',
            'national_number': '1234567890',
            'email': 'missingcode@example.com',
            'address': '123 Test St',
            'notes': '',
            'is_active': True
        }
        form = DentalLabForm(data=form_data_missing_code)
        self.assertFalse(form.is_valid())
        self.assertIn('country_code', form.errors)

    def test_dental_lab_form_phone_number_cross_check(self):
        # Test phone number conflict with existing DentalLab
        form_data_lab_conflict = {
            'name': 'Conflicting Lab',
            'contact_person': 'Test Contact',
            'country_code': '91',
            'national_number': '9876543213', # Same as self.lab
            'email': 'conflictlab@example.com',
            'address': '123 Test St',
            'notes': '',
            'is_active': True
        }
        form = DentalLabForm(data=form_data_lab_conflict)
        self.assertFalse(form.is_valid())
        self.assertIn('national_number', form.errors)
        self.assertIn(f"This phone number is already in use by dental lab: {self.lab.name}.", form.errors['national_number'][0])

        # Test phone number conflict with StaffMember
        form_data_staff_conflict = {
            'name': 'Staff Conflict Lab',
            'contact_person': 'Test Contact',
            'country_code': '91',
            'national_number': '9876543210', # Same as self.doctor
            'email': 'staffconflict@example.com',
            'address': '123 Test St',
            'notes': '',
            'is_active': True
        }
        form = DentalLabForm(data=form_data_staff_conflict)
        self.assertFalse(form.is_valid())
        self.assertIn('national_number', form.errors)
        self.assertIn(f"This phone number is already in use by staff: {self.doctor.user.get_full_name()}.", form.errors['national_number'][0])

        # Test phone number conflict with Patient
        form_data_patient_conflict = {
            'name': 'Patient Conflict Lab',
            'contact_person': 'Test Contact',
            'country_code': '91',
            'national_number': '9876543211', # Same as self.patient
            'email': 'patientconflict@example.com',
            'address': '123 Test St',
            'notes': '',
            'is_active': True
        }
        form = DentalLabForm(data=form_data_patient_conflict)
        self.assertFalse(form.is_valid())
        self.assertIn('national_number', form.errors)
        self.assertIn(f"This phone number is already in use by patient: {self.patient.name}.", form.errors['national_number'][0])

        # Test phone number conflict with Supplier
        form_data_supplier_conflict = {
            'name': 'Supplier Conflict Lab',
            'contact_person': 'Test Contact',
            'country_code': '91',
            'national_number': '9876543212', # Same as self.supplier
            'email': 'supplierconflict@example.com',
            'address': '123 Test St',
            'notes': '',
            'is_active': True
        }
        form = DentalLabForm(data=form_data_supplier_conflict)
        self.assertFalse(form.is_valid())
        self.assertIn('national_number', form.errors)
        self.assertIn(f"This phone number is already in use by supplier: {self.supplier.name}.", form.errors['national_number'][0])

    def test_dental_lab_form_email_uniqueness_check_only_within_labs(self):
        # Test email conflict with existing DentalLab
        form_data_lab_email_conflict = {
            'name': 'Conflicting Lab Email',
            'contact_person': 'Test Contact',
            'country_code': '91',
            'national_number': '9876540003', # Using a new valid number
            'email': 'brightlab@example.com', # Same as self.lab
            'address': '123 Test St',
            'notes': '',
            'is_active': True
        }
        form = DentalLabForm(data=form_data_lab_email_conflict)
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)
        self.assertIn(f"This email address is already in use by dental lab: {self.lab.name}.", form.errors['email'][0])

        # Test email that exists in Staff/Patient/Supplier but should be valid for a new lab (no cross-app email validation for labs)
        form_data_external_email = {
            'name': 'External Email Lab',
            'contact_person': 'Test Contact',
            'country_code': '91',
            'national_number': '9876540004', # Using a new valid number
            'email': 'doc@example.com', # Exists in Staff but should pass
            'address': '123 Test St',
            'notes': '',
            'is_active': True
        }
        form = DentalLabForm(data=form_data_external_email)
        self.assertTrue(form.is_valid(), form.errors)

    def test_dental_lab_form_initial_data_on_edit(self):
        lab = DentalLab.objects.create(name='Existing Lab', contact_number=PhoneNumber.from_string('+12125551234'), email='existing@example.com')
        form = DentalLabForm(instance=lab)
        self.assertEqual(form.fields['country_code'].initial, '1')
        self.assertEqual(form.fields['national_number'].initial, '2125551234')
        self.assertEqual(form.initial['email'], 'existing@example.com')

    def test_add_lab_view_with_new_features(self):
        add_lab_url = reverse('lab_cases:add_lab')
        valid_data = {
            'name': 'New Unique Lab',
            'contact_person': 'Jane Smith',
            'country_code': '91',
            'national_number': '9876540005', # Changed to a new unique number
            'email': 'newuniquelab@example.com',
            'address': '123 New St',
            'notes': 'Some notes',
            'is_active': 'on'
        }
        response = self.client.post(add_lab_url, valid_data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(DentalLab.objects.filter(name='New Unique Lab').exists())
        new_lab = DentalLab.objects.get(name='New Unique Lab')
        self.assertEqual(str(new_lab.contact_number), '+919876540005')
        self.assertEqual(new_lab.email, 'newuniquelab@example.com')

        # Test invalid data (duplicate phone)
        invalid_data_dup_phone = valid_data.copy()
        invalid_data_dup_phone['name'] = 'Another Lab'
        invalid_data_dup_phone['contact_person'] = 'Another Contact'
        invalid_data_dup_phone['email'] = 'anotherlab@example.com'
        response = self.client.post(add_lab_url, invalid_data_dup_phone)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This phone number is already in use by dental lab: New Unique Lab.')
        self.assertFalse(DentalLab.objects.filter(name='Another Lab').exists())

        # Test invalid data (duplicate email within labs)
        invalid_data_dup_email = valid_data.copy()
        invalid_data_dup_email['name'] = 'Yet Another Lab'
        invalid_data_dup_email['contact_person'] = 'Yet Another Contact'
        invalid_data_dup_email['country_code'] = '91'
        invalid_data_dup_email['national_number'] = '9876540006' # Changed to a new unique number
        response = self.client.post(add_lab_url, invalid_data_dup_email)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This email address is already in use by dental lab: New Unique Lab.')
        self.assertFalse(DentalLab.objects.filter(name='Yet Another Lab').exists())

    def test_edit_lab_view_with_new_features(self):
        edit_lab_url = reverse('lab_cases:edit_lab', args=[self.lab.pk])
        
        # Test valid update
        valid_update_data = {
            'name': self.lab.name,
            'contact_person': 'Updated Contact',
            'country_code': '91',
            'national_number': '9998887770',
            'email': 'updated_brightlab@example.com',
            'address': 'Updated Address',
            'notes': 'Updated notes',
            'is_active': 'on' if self.lab.is_active else ''
        }
        response = self.client.post(edit_lab_url, valid_update_data)
        self.assertEqual(response.status_code, 302)
        self.lab.refresh_from_db()
        self.assertEqual(str(self.lab.contact_number), '+919998887770')
        self.assertEqual(self.lab.contact_person, 'Updated Contact')
        self.assertEqual(self.lab.email, 'updated_brightlab@example.com')

        # Test update with duplicate phone (conflict with another lab)
        other_lab = DentalLab.objects.create(name='Another Existing Lab', contact_number=PhoneNumber.from_string('+919998887771'), email='anotherlab@example.com')
        invalid_update_data_dup_phone = valid_update_data.copy()
        invalid_update_data_dup_phone['national_number'] = '9998887771'
        invalid_update_data_dup_phone['email'] = 'another_unique_email_for_dup_phone@example.com' # Make email unique for this test
        response = self.client.post(edit_lab_url, invalid_update_data_dup_phone)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"This phone number is already in use by dental lab: {other_lab.name}.")
        
        # Test update with duplicate email (within labs, not cross-app)
        invalid_update_data_dup_email = valid_update_data.copy()
        invalid_update_data_dup_email['national_number'] = '9998887772'
        invalid_update_data_dup_email['email'] = 'anotherlab@example.com'
        response = self.client.post(edit_lab_url, invalid_update_data_dup_email)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"This email address is already in use by dental lab: {other_lab.name}.")