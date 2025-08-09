from django import forms
from django.forms import inlineformset_factory
from .models import DentalRecord, Prescription, PrescriptionItem

class DentalRecordForm(forms.ModelForm):
    class Meta:
        model = DentalRecord
        fields = ['clinical_notes', 'treatments_performed']
        widgets = {
            'clinical_notes': forms.Textarea(attrs={'rows': 5, 'class': 'form-control', 'placeholder': "Enter clinical notes, observations, diagnosis..."}),
            'treatments_performed': forms.Textarea(attrs={'rows': 5, 'class': 'form-control', 'placeholder': "Detail treatments performed..."}),
        }
        labels = {
            'clinical_notes': 'Clinical Notes & Diagnosis',
            'treatments_performed': 'Treatments Performed',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if 'class' not in field.widget.attrs:
                field.widget.attrs.update({'class': 'form-control'})

class PrescriptionForm(forms.ModelForm):
    class Meta:
        model = Prescription
        fields = ['notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Optional general notes for the whole prescription...'}),
        }

class PrescriptionItemForm(forms.ModelForm):
    class Meta:
        model = PrescriptionItem
        fields = ['medication_name', 'dosage', 'frequency', 'duration', 'notes']
        widgets = {
            'medication_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Amoxicillin'}),
            'dosage': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 500mg'}),
            'frequency': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 1 tablet 3 times a day'}),
            'duration': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., for 5 days'}),
            'notes': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional notes, e.g., after food'}),
        }

PrescriptionItemFormSet = inlineformset_factory(
    Prescription,
    PrescriptionItem,
    form=PrescriptionItemForm,
    fields=['medication_name', 'dosage', 'frequency', 'duration', 'notes'],
    extra=0,
    can_delete=True,
    can_delete_extra=True
)
