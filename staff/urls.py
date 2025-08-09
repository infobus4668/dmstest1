# DENTALCLINICSYSTEM/staff/urls.py

from django.urls import path
from . import views

app_name = 'staff'

urlpatterns = [
    path('', views.staff_list, name='staff_list'),
    path('add/', views.add_staff_member, name='add_staff_member'),
    # pk is normalized
    path('<int:pk>/edit/', views.edit_staff_member, name='edit_staff_member'),
    path('<int:pk>/delete/', views.delete_staff_member, name='delete_staff_member'),
]