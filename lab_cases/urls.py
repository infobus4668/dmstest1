# DENTALCLINICSYSTEM/lab_cases/urls.py

from django.urls import path
from . import views

app_name = 'lab_cases'

urlpatterns = [
    # --- Dental Lab URLs ---
    path('labs/', views.lab_list_view, name='lab_list'),
    path('labs/add/', views.add_lab_view, name='add_lab'),
    path('labs/<int:pk>/edit/', views.edit_lab_view, name='edit_lab'),
    path('labs/<int:pk>/delete/', views.delete_lab_view, name='delete_lab'),

    # --- Lab Case URLs ---
    path('cases/', views.lab_case_list_view, name='lab_case_list'),
    path('cases/add/', views.add_lab_case_view, name='add_lab_case'),
    # NORMALIZED: The URL now uses the standard 'pk' convention.
    path('cases/add/from-appointment/<int:pk>/', views.add_lab_case_view, name='add_lab_case_from_appointment'),
    path('cases/<int:pk>/', views.lab_case_detail_view, name='lab_case_detail'),
    path('cases/<int:pk>/edit/', views.edit_lab_case_view, name='edit_lab_case'),
    path('cases/<int:pk>/delete/', views.delete_lab_case_view, name='delete_lab_case'),
    
    path('cases/<int:pk>/add-payment/', views.add_lab_payment_view, name='add_lab_payment'),
]