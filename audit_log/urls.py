# audit_log/urls.py

from django.urls import path
from . import views

app_name = 'audit_log'

urlpatterns = [
    path('', views.role_change_log_view, name='role_change_log'),
]