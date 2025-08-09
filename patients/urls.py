# DENTALCLINICSYSTEM/patients/urls.py

from django.urls import path
from . import views

app_name = 'patients'

urlpatterns = [
    # Corrected view name from 'patient_list_view' to 'patient_list'
    path('', views.patient_list, name='patient_list'), 
    path('add/', views.add_patient, name='add_patient'),
    path('<int:pk>/', views.patient_detail, name='patient_detail'),
    path('<int:pk>/edit/', views.edit_patient, name='edit_patient'),
    path('<int:pk>/delete/', views.delete_patient, name='delete_patient'),
]