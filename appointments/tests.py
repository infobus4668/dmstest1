from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils import timezone
from datetime import timedelta
from appointments.models import Appointment
from patients.models import Patient
from staff.models import StaffMember
from django.conf import settings


User = get_user_model()

@override_settings(
    MIDDLEWARE=[m for m in settings.MIDDLEWARE if 'audit_log.middleware.RequestUserMiddleware' not in m],
    INSTALLED_APPS=[app for app in settings.INSTALLED_APPS if app != 'audit_log']
)
class AppointmentTestSuite(TestCase):
    def setUp(self):
        self.client = Client()
        self.password = 'StrongPassword123'
        self.doctor_user = User.objects.create_user(username='doctor', password=self.password, is_active=True)
        self.doctor_group, _ = Group.objects.get_or_create(name='Doctors')
        self.doctor_user.groups.add(self.doctor_group)
        self.doctor_staff = StaffMember.objects.create(user=self.doctor_user, is_active=True)
        self.doctor_user.doctor_profile = self.doctor_staff
        self.doctor_user.save()

        self.patient = Patient.objects.create(name='John Doe', date_of_birth='1990-01-01')

        self.superuser = User.objects.create_superuser(username='admin', password=self.password, is_active=True)
        self.client.login(username='admin', password=self.password)

        self.appointment = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor_staff,
            appointment_datetime=timezone.now() + timedelta(days=1),
            reason='Routine Checkup',
            status='SCH'
        )

    def test_appointment_list_view(self):
        response = self.client.get(reverse('appointments:appointment_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'List of Appointments')

    def test_schedule_appointment_view(self):
        response = self.client.get(reverse('appointments:schedule_appointment'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Schedule New Appointment')

        response_post = self.client.post(reverse('appointments:schedule_appointment'), {
            'patient': self.patient.pk,
            'doctor': self.doctor_staff.pk,
            'appointment_datetime': (timezone.now() + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M'),
            'reason': 'Toothache',
            'status': 'CNF'
        }, follow=True)
        self.assertEqual(response_post.status_code, 200)
        self.assertContains(response_post, 'Appointment scheduled successfully!')

    def test_appointment_detail_view(self):
        response = self.client.get(reverse('appointments:appointment_detail', args=[self.appointment.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.patient.name)

    def test_edit_appointment_view(self):
        response = self.client.post(reverse('appointments:edit_appointment', args=[self.appointment.pk]), {
            'patient': self.patient.pk,
            'doctor': self.doctor_staff.pk,
            'appointment_datetime': (timezone.now() + timedelta(days=3)).strftime('%Y-%m-%dT%H:%M'),
            'reason': 'Updated Reason',
            'status': 'CMP'
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Appointment details updated successfully!')

    def test_delete_appointment_view(self):
        response = self.client.post(reverse('appointments:delete_appointment', args=[self.appointment.pk]), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Appointment deleted successfully!')
        self.assertFalse(Appointment.objects.filter(pk=self.appointment.pk).exists())

    def test_api_all_view(self):
        response = self.client.get(reverse('appointments:appointment_api_view'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json())

    def test_print_summary_view(self):
        response = self.client.get(reverse('appointments:print_summary', args=[self.appointment.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.patient.name)

    def test_print_bill_summary_view(self):
        response = self.client.get(reverse('appointments:print_bill_summary', args=[self.appointment.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.patient.name)
