# DENTALCLINICSYSTEM/reporting/forms.py

from django import forms
from billing.models import Supplier, Product
from lab_cases.models import DentalLab, LabCase
from patients.models import Patient

# UPDATED: This form now uses a single CharField for the date range picker.
class ReportFilterForm(forms.Form):
    date_range = forms.CharField(
        label="Date Range",
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'id': 'report_date_range'})
    )
    supplier = forms.ModelChoiceField(
        queryset=Supplier.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control select2-enable'})
    )
    product = forms.ModelChoiceField(
        queryset=Product.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control select2-enable'})
    )
    lab = forms.ModelChoiceField(
        queryset=DentalLab.objects.all(),
        required=False,
        label="Lab",
        widget=forms.Select(attrs={'class': 'form-control select2-enable'})
    )
    patient = forms.ModelChoiceField(
        queryset=Patient.objects.all(),
        required=False,
        label="Patient Name",
        widget=forms.Select(attrs={'class': 'form-control select2-enable'})
    )
    status = forms.ChoiceField(
        label="Status",
        choices=[('', 'All Statuses')] + LabCase.CASE_STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        hide_supplier = kwargs.pop('hide_supplier', False)
        hide_product = kwargs.pop('hide_product', False)
        hide_lab = kwargs.pop('hide_lab', False)
        hide_patient = kwargs.pop('hide_patient', False)
        hide_status = kwargs.pop('hide_status', False)
        super().__init__(*args, **kwargs)

        if hide_supplier: del self.fields['supplier']
        if hide_product: del self.fields['product']
        if hide_lab: del self.fields['lab']
        if hide_patient: del self.fields['patient']
        if hide_status: del self.fields['status']