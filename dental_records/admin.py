from django.contrib import admin
from .models import DentalRecord, Prescription, PrescriptionItem

class PrescriptionItemInline(admin.TabularInline):
    model = PrescriptionItem
    extra = 1
    fields = ('medication_name', 'dosage', 'frequency', 'duration', 'notes')

class PrescriptionAdmin(admin.ModelAdmin):
    inlines = [PrescriptionItemInline]
    list_display = ('__str__', 'date_prescribed')
    search_fields = ('dental_record__appointment__patient__name',)

class PrescriptionInline(admin.StackedInline):
    model = Prescription
    can_delete = False
    verbose_name_plural = 'Prescription'
    fields = ('notes',)

class DentalRecordAdmin(admin.ModelAdmin):
    list_display = ('get_appointment_patient', 'get_appointment_doctor', 'get_appointment_datetime', 'created_at')
    list_filter = ('appointment__appointment_datetime', 'appointment__doctor')
    search_fields = ('appointment__patient__name', 'appointment__doctor__name', 'clinical_notes', 'treatments_performed')
    raw_id_fields = ('appointment',)
    inlines = [PrescriptionInline]

    def get_appointment_patient(self, obj):
        return obj.appointment.patient.name
    get_appointment_patient.short_description = 'Patient'
    get_appointment_patient.admin_order_field = 'appointment__patient__name'

    def get_appointment_doctor(self, obj):
        return f"Dr. {obj.appointment.doctor.name}"
    get_appointment_doctor.short_description = 'Doctor'
    get_appointment_doctor.admin_order_field = 'appointment__doctor__name'

    def get_appointment_datetime(self, obj):
        return obj.appointment.appointment_datetime
    get_appointment_datetime.short_description = 'Appointment Time'
    get_appointment_datetime.admin_order_field = 'appointment__appointment_datetime'

try:
    admin.site.unregister(DentalRecord)
except admin.sites.NotRegistered:
    pass
admin.site.register(DentalRecord, DentalRecordAdmin)

admin.site.register(Prescription, PrescriptionAdmin)
