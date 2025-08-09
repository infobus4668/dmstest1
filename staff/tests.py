# DENTALCLINICSYSTEM/staff/tests.py

from django.test import TestCase, Client, override_settings
from django.urls import reverse
from datetime import date
from phonenumber_field.phonenumber import PhoneNumber
from django.core.exceptions import ValidationError
from django.conf import settings # Ensure settings is imported

# Import models for cross-checking
from .models import StaffMember
from .forms import StaffMemberForm
from patients.models import Patient
from billing.models import Supplier
from lab_cases.models import DentalLab
from django.contrib.auth import get_user_model
User = get_user_model()
from django.contrib.auth.models import Group # Import Group model

# Temporarily remove audit_log middleware for the test class
@override_settings(
    MIDDLEWARE=[m for m in settings.MIDDLEWARE if m != 'audit_log.middleware.RequestUserMiddleware']
)
class StaffMemberFormValidationTests(TestCase):

    @classmethod
    def setUpTestData(cls): # This method runs ONCE for the entire test class
        super().setUpTestData()
        
        # 1. Create groups once for all tests in this class
        cls.receptionists_group, _ = Group.objects.get_or_create(name='Receptionists')
        cls.doctors_group, _ = Group.objects.get_or_create(name='Doctors')
        cls.managers_group, _ = Group.objects.get_or_create(name='Managers')

        # 2. Create users once, so their PKs are stable throughout the test run
        cls.admin_user_test = User.objects.create_user(username='admin_test', password='password', email='admin_test@example.com')
        cls.admin_user_test.is_staff = True
        cls.admin_user_test.is_superuser = True
        cls.admin_user_test.save()
        cls.admin_user_test.groups.add(cls.managers_group) 

        # FIX: Ensure first_name and last_name are set for the staff user instance
        cls.staff_user_for_instance_test = User.objects.create_user(
            username='staff_test',
            password='password123',
            email='staff_test@example.com',
            first_name='Staff', # ADDED
            last_name='Member' # ADDED
        )
        cls.staff_user_for_instance_test.is_active = True
        cls.staff_user_for_instance_test.save()
        cls.staff_user_for_instance_test.groups.add(cls.receptionists_group)

        # 3. Create StaffMember instance once using the pre-created user
        cls.staff_member_instance = StaffMember.objects.create(
            user=cls.staff_user_for_instance_test,
            contact_number=PhoneNumber.from_string('+919876543000'),
            date_joined=date(2023, 1, 1),
            is_active=True
        )

        # 4. Create cross-app fixtures once (Patient, Supplier, DentalLab)
        cls.patient = Patient.objects.create(
            name='Test Patient',
            date_of_birth=date(1990, 1, 1),
            gender='M',
            contact_number=PhoneNumber.from_string('+919876543001'),
            place='Chennai',
        )
        cls.supplier = Supplier.objects.create(
            name='Test Supplier',
            category='SERVICES',
            phone_number=PhoneNumber.from_string('+919876543002'),
            email='supplier@example.com'
        )
        cls.dental_lab = DentalLab.objects.create(
            name='Test Dental Lab',
            contact_number=PhoneNumber.from_string('+919876543003'),
            email='dentallab@example.com'
        )


    def setUp(self): # This method runs BEFORE EACH test method
        self.client = Client()
        self.client.force_login(self.admin_user_test) # Force login the pre-created admin user
        
        # Access pre-created instances from setUpTestData
        self.staff_member = self.staff_member_instance # Refer to the class-level instance
        self.patient = self.patient # Refer to the class-level instance
        self.supplier = self.supplier # Refer to the class-level instance
        self.dental_lab = self.dental_lab # Refer to the class-level instance
        self.receptionists_group = self.receptionists_group # Refer to the class-level instance


        # Base valid data for forms (for NEW staff members)
        self.valid_form_data = {
            'first_name': 'New',
            'last_name': 'Staff',
            'email': 'newstaff@example.com', # Unique email
            'username': 'newstaff_unique', # Unique username
            'password': 'newpassword123',
            'groups': [self.receptionists_group.pk], # Use PK from pre-created group
            'country_code': '91',
            'national_number': '9876543004', # Unique number
            'address': '123 Test St',
            'date_of_birth': '1990-01-01',
            'is_active': True,
            'specialization': '',
            'credentials': ''
        }

    # Helper to construct data for edit tests
    def _get_edit_data(self, staff_member_instance, new_phone_number=None, new_email=None, new_username=None, new_password=None):
        # Start with fields directly from the User model (ensuring they are not None)
        data = {
            'first_name': staff_member_instance.user.first_name if staff_member_instance.user.first_name is not None else '',
            'last_name': staff_member_instance.user.last_name if staff_member_instance.user.last_name is not None else '',
            'email': staff_member_instance.user.email if staff_member_instance.user.email is not None else '',
            'username': staff_member_instance.user.username if staff_member_instance.user.username is not None else '',
            'password': '', # Always start with an empty password unless explicitly provided
            'groups': [g.pk for g in staff_member_instance.user.groups.all()], # Always ensure groups are passed as PKs
        }

        # Add/override StaffMember fields
        data.update({
            'address': staff_member_instance.address if staff_member_instance.address is not None else '',
            'date_of_birth': staff_member_instance.date_of_birth.isoformat() if staff_member_instance.date_of_birth else '', # Convert date to string
            'is_active': staff_member_instance.is_active,
            'specialization': staff_member_instance.specialization if staff_member_instance.specialization is not None else '',
            'credentials': staff_member_instance.credentials if staff_member_instance.credentials is not None else '',
        })
        
        # Override with new values if provided
        if new_email is not None:
            data['email'] = new_email
        if new_username is not None:
            data['username'] = new_username
        if new_password is not None:
            data['password'] = new_password
        
        # Handle phone number parts
        if new_phone_number:
            phone_obj = PhoneNumber.from_string(new_phone_number)
            data['country_code'] = str(phone_obj.country_code)
            data['national_number'] = str(phone_obj.national_number)
        elif staff_member_instance.contact_number:
            data['country_code'] = str(staff_member_instance.contact_number.country_code)
            data['national_number'] = str(staff_member_instance.contact_number.national_number)
        else: # If no phone number is present and no new one provided
            data['country_code'] = ''
            data['national_number'] = ''
        
        return data

    def test_staff_member_form_valid_phone_number(self):
        """Test form with a valid and unique phone number."""
        form = StaffMemberForm(data=self.valid_form_data)
        self.assertTrue(form.is_valid(), form.errors)
        staff_member = form.save()
        self.assertEqual(str(staff_member.contact_number), '+919876543004')
        self.assertEqual(staff_member.user.email, 'newstaff@example.com')
    
    def test_staff_member_form_phone_number_not_valid_for_country(self):
        """Test a phone number that is not valid for the selected country (e.g., wrong length/format)."""
        form_data = self.valid_form_data.copy()
        form_data['email'] = 'invalid_phone@example.com'
        form_data['username'] = 'invalid_phone_user'
        form_data['country_code'] = '91'
        form_data['national_number'] = '123' # Too short for India
        form = StaffMemberForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('national_number', form.errors)
        self.assertIn('The phone number is not valid for the selected country.', form.errors['national_number'])

    # Phone number conflict tests
    def test_staff_member_form_phone_number_conflict_with_patient(self):
        """Test phone number conflict with an existing Patient."""
        data = self.valid_form_data.copy()
        data['national_number'] = '9876543001' # Patient's number
        data['email'] = 'anotheremail@example.com' # Ensure email is unique
        data['username'] = 'anotheruser'
        form = StaffMemberForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('national_number', form.errors)
        self.assertIn(f"This phone number is already in use by patient: {self.patient.name}.", form.errors['national_number'])

    def test_staff_member_form_phone_number_conflict_with_supplier(self):
        """Test phone number conflict with an existing Supplier."""
        data = self.valid_form_data.copy()
        data['national_number'] = '9876543002' # Supplier's number
        data['email'] = 'yetanotheremail@example.com' # Ensure email is unique
        data['username'] = 'yetanotheruser'
        form = StaffMemberForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('national_number', form.errors)
        self.assertIn(f"This phone number is already in use by supplier: {self.supplier.name}.", form.errors['national_number'])

    def test_staff_member_form_phone_number_conflict_with_dental_lab(self):
        """Test phone number conflict with an existing DentalLab."""
        data = self.valid_form_data.copy()
        data['national_number'] = '9876543003' # DentalLab's number
        data['email'] = 'labconflict@example.com' # Ensure email is unique
        data['username'] = 'labuser'
        form = StaffMemberForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('national_number', form.errors)
        self.assertIn(f"This phone number is already in use by dental lab: {self.dental_lab.name}.", form.errors['national_number'])

    def test_staff_member_form_edit_own_phone_number(self):
        """Test editing a staff member without changing their phone number."""
        data = self._get_edit_data(self.staff_member)
        form = StaffMemberForm(data=data, instance=self.staff_member)
        self.assertTrue(form.is_valid(), form.errors)
        updated_staff = form.save()
        self.assertEqual(str(updated_staff.contact_number), '+919876543000')

    def test_staff_member_form_edit_new_unique_phone_number(self):
        """Test editing a staff member with a new unique phone number."""
        data = self._get_edit_data(self.staff_member, new_phone_number='+919876543999')
        form = StaffMemberForm(data=data, instance=self.staff_member)
        self.assertTrue(form.is_valid(), form.errors)
        updated_staff = form.save()
        self.assertEqual(str(updated_staff.contact_number), '+919876543999')

    def test_staff_member_form_edit_phone_number_conflict_with_dental_lab(self):
        """Test editing staff member with phone number conflict with DentalLab."""
        data = self._get_edit_data(self.staff_member, new_phone_number='+919876543003') # DentalLab's number
        form = StaffMemberForm(data=data, instance=self.staff_member)
        self.assertFalse(form.is_valid())
        self.assertIn('national_number', form.errors)
        self.assertIn(f"This phone number is already in use by dental lab: {self.dental_lab.name}.", form.errors['national_number'])

    # Email Cross-Check Tests
    def test_staff_member_form_email_conflict_with_supplier(self):
        """Test email conflict with an existing Supplier."""
        data = self._get_edit_data(self.staff_member, new_email='supplier@example.com', new_phone_number='+919876543006')
        form = StaffMemberForm(data=data, instance=self.staff_member) # Pass instance for edit tests
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)
        self.assertIn(f"This email address is already in use by supplier: {self.supplier.name}.", form.errors['email'])

    def test_staff_member_form_email_conflict_with_dental_lab(self):
        """Test email conflict with an existing DentalLab."""
        data = self._get_edit_data(self.staff_member, new_email='dentallab@example.com', new_phone_number='+919876543007')
        form = StaffMemberForm(data=data, instance=self.staff_member) # Pass instance for edit tests
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)
        self.assertIn(f"This email address is already in use by dental lab: {self.dental_lab.name}.", form.errors['email'])

    # View-level tests for add/edit staff members
    def test_add_staff_member_view_valid_data(self):
        url = reverse('staff:add_staff_member')
        data = self.valid_form_data.copy()
        data['national_number'] = '9876543008' # Ensure unique for this view test
        data['email'] = 'viewaddstaff@example.com' # Ensure unique email for view test
        data['username'] = 'viewaddstaff' # Ensure unique username for view test
        response = self.client.post(url, data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Staff member added successfully.")
        self.assertTrue(StaffMember.objects.filter(user__username='viewaddstaff').exists())
        self.assertEqual(str(StaffMember.objects.get(user__username='viewaddstaff').contact_number), '+919876543008')
        self.assertEqual(StaffMember.objects.get(user__username='viewaddstaff').user.email, 'viewaddstaff@example.com')

    def test_add_staff_member_view_duplicate_phone_error(self):
        url = reverse('staff:add_staff_member')
        data = self.valid_form_data.copy()
        data['national_number'] = '9876543001' # Patient's number
        data['email'] = 'dup_phone_add@example.com' # Ensure email is unique for this specific test
        data['username'] = 'dup_phone_add'
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"This phone number is already in use by patient: {self.patient.name}.")
        self.assertFalse(StaffMember.objects.filter(user__username='dup_phone_add').exists())

    def test_add_staff_member_view_duplicate_email_error(self):
        url = reverse('staff:add_staff_member')
        data = self.valid_form_data.copy()
        data['email'] = 'supplier@example.com' # Supplier's email
        data['national_number'] = '9876543009' # Unique phone number
        data['username'] = 'dup_email_add'
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"This email address is already in use by supplier: {self.supplier.name}.")
        self.assertFalse(StaffMember.objects.filter(user__username='dup_email_add').exists())

    def test_edit_staff_member_view_duplicate_phone_error(self):
        url = reverse('staff:edit_staff_member', args=[self.staff_member.pk])
        data = self._get_edit_data(self.staff_member, new_phone_number='+919876543001') # Patient's number
        response = self.client.post(url, data) 
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"This phone number is already in use by patient: {self.patient.name}.")
        self.staff_member.refresh_from_db()
        self.assertEqual(str(self.staff_member.contact_number), '+919876543000')

    def test_edit_staff_member_view_duplicate_email_error(self):
        url = reverse('staff:edit_staff_member', args=[self.staff_member.pk])
        data = self._get_edit_data(self.staff_member, new_email='supplier@example.com', new_phone_number='+919876543010')
        response = self.client.post(url, data) 
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"This email address is already in use by supplier: {self.supplier.name}.")
        self.staff_member.refresh_from_db()
        self.assertNotEqual(self.staff_member.user.email, 'supplier@example.com')