# DENTALCLINICSYSTEM/patients/admin.py

from django.contrib import admin
from .models import Patient

class PatientAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_number', 'place', 'age', 'updated_at')
    search_fields = ('name', 'contact_number', 'place')

admin.site.register(Patient, PatientAdmin)