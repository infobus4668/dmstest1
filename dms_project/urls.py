# DENTALCLINICSYSTEM/dms_project/urls.py

from django.contrib import admin
from django.urls import path, include # Make sure 'include' is imported
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from dashboard.views import dashboard_view

urlpatterns = [
    path('admin/', admin.site.urls),

    # Dashboard URL
    path('', dashboard_view, name='dashboard'),

    # django-select2 URL
    path("select2/", include("django_select2.urls")), # <-- ADD THIS LINE

    # App-specific URLs
    path('patients/', include('patients.urls')),
    path('appointments/', include('appointments.urls')),
    path('billing/', include('billing.urls')),
    path('dental-records/', include('dental_records.urls')),
    path('lab-cases/', include('lab_cases.urls')),
    path('staff/', include('staff.urls')),
    path('reporting/', include('reporting.urls')),
    path('audit/', include('audit_log.urls')),

    # Authentication URLs - Grouped under 'accounts/' for consistency
    path('accounts/login/', auth_views.LoginView.as_view(), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('accounts/password_reset/',
         auth_views.PasswordResetView.as_view(),
         name='password_reset'),
    path('accounts/password_reset/done/',
         auth_views.PasswordResetDoneView.as_view(),
         name='password_reset_done'),
    path('accounts/reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(),
         name='password_reset_confirm'),
    path('accounts/reset/done/',
         auth_views.PasswordResetCompleteView.as_view(),
         name='password_reset_complete'),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Custom error handler for 403 Forbidden errors
handler403 = 'dashboard.views.custom_permission_denied_view'