from django.urls import path
from . import views

app_name = 'appointments'

urlpatterns = [
    # API endpoint for the calendar
    path('api/all/', views.appointment_api_view, name='appointment_api_view'),

    # Regular appointment views
    path('', views.appointment_list_view, name='appointment_list'),
    path('schedule/', views.schedule_appointment_view, name='schedule_appointment'),

    # Primary key normalized views (already using <int:pk>)
    path('<int:pk>/', views.appointment_detail_view, name='appointment_detail'),
    path('<int:pk>/edit/', views.edit_appointment_view, name='edit_appointment'),
    path('<int:pk>/delete/', views.delete_appointment_view, name='delete_appointment'),

    # Print views
    path('<int:pk>/print-summary/', views.print_summary_view, name='print_summary'),
    path('<int:pk>/print-bill-summary/', views.print_bill_summary_view, name='print_bill_summary'),
]