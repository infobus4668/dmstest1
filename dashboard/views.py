# DENTALCLINICSYSTEM/dashboard/views.py

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
import json

from appointments.models import Appointment
from patients.models import Patient
from staff.models import StaffMember
from lab_cases.models import LabCase
from billing.models import Invoice, ProductVariant
from django.db.models import Sum, F
from django.db.models.functions import Coalesce
from django.urls import reverse

@login_required
def dashboard_view(request):
    user = request.user

    # --- FINAL FIX FOR MISSING STAFF PROFILES ---
    if user.is_staff and not hasattr(user, 'staff_profile'):
        StaffMember.objects.create(user=user)
        user.refresh_from_db()
    # --- END OF FIX ---

    all_appointments = Appointment.objects.all()
    all_invoices = Invoice.objects.all()
    all_lab_cases = LabCase.objects.all()

    if hasattr(user, 'staff_profile') and user.groups.filter(name='Doctors').exists():
        appointments_qs = all_appointments.filter(doctor=user.staff_profile)
        invoices_qs = all_invoices.filter(doctor=user.staff_profile)
        lab_cases_qs = all_lab_cases.filter(doctor=user.staff_profile)
    else:
        appointments_qs = all_appointments
        invoices_qs = all_invoices
        lab_cases_qs = all_lab_cases

    today = timezone.now().date()
    todays_appointments_count = appointments_qs.filter(appointment_datetime__date=today).count()
    upcoming_appointments_count = appointments_qs.filter(appointment_datetime__date__gt=today).count()

    outstanding_invoices = invoices_qs.filter(status__in=['PENDING', 'PARTIAL'])
    total_outstanding_balance = sum(invoice.balance_due for invoice in outstanding_invoices)

    pending_lab_cases_count = lab_cases_qs.filter(status__in=['CREATED', 'SENT']).count()

    # --- Updated Calendar Events with Tooltip Data ---
    calendar_events = []
    for appt in appointments_qs.select_related('patient', 'doctor__user'):
        calendar_events.append({
            'id': appt.pk,
            'title': f"{appt.patient.name} ({appt.get_status_display()})",
            'start': appt.appointment_datetime.isoformat(),
            'end': (appt.appointment_datetime + timedelta(minutes=30)).isoformat(),
            'url': reverse('appointments:appointment_detail', args=[appt.pk]),
            'extendedProps': {
                'doctor': str(appt.doctor) if appt.doctor else 'N/A',
                'patient': appt.patient.name,
                'time': appt.appointment_datetime.strftime('%I:%M %p'),
                'status': appt.get_status_display(),
            }
        })

    context = {
        'page_title': 'Dashboard',
        'todays_appointments_count': todays_appointments_count,
        'upcoming_appointments_count': upcoming_appointments_count,
        'total_outstanding_balance': total_outstanding_balance,
        'pending_lab_cases_count': pending_lab_cases_count,
        'low_stock_products_count': ProductVariant.objects.annotate(
            current_stock=Sum('stock_items__quantity', default=0) - Coalesce(Sum('stock_items__transactions__quantity'), 0)
        ).filter(is_active=True, current_stock__lte=F('low_stock_threshold')).count(),
        'total_patients_count': Patient.objects.count(),
        'calendar_events_json': json.dumps(calendar_events),
    }

    return render(request, 'dashboard/dashboard.html', context)


def custom_permission_denied_view(request, exception=None):
    return render(request, "403.html", status=403)
