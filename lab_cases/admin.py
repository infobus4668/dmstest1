# lab_cases/admin.py

from django.contrib import admin
from .models import DentalLab, LabCase, LabPayment
from .forms import DentalLabForm # Added import

class DentalLabAdmin(admin.ModelAdmin):
    form = DentalLabForm # Use the custom form
    list_display = ('name', 'contact_person', 'contact_number', 'email', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'contact_person', 'contact_number', 'email', 'notes')
    list_editable = ('is_active',)
    list_per_page = 20

class LabPaymentInline(admin.TabularInline):
    model = LabPayment
    extra = 0
    readonly_fields = ('payment_date',)

class LabCaseAdmin(admin.ModelAdmin):
    list_display = ('case_type', 'patient', 'lab', 'status', 'cost_per_unit', 'units', 'total_cost', 'balance_due')
    list_filter = ('status', 'lab', 'date_sent', 'date_due', 'doctor')
    search_fields = (
        'case_type', 'description', 'patient__name',
        'doctor__user__first_name', 'doctor__user__last_name', 
        'lab__name',
    )
    raw_id_fields = ('patient', 'doctor', 'lab')
    date_hierarchy = 'date_sent'
    list_per_page = 25
    inlines = [LabPaymentInline]
    readonly_fields = ('subtotal', 'gst_amount', 'total_cost', 'amount_paid', 'balance_due')

admin.site.register(DentalLab, DentalLabAdmin)
admin.site.register(LabCase, LabCaseAdmin)
admin.site.register(LabPayment)