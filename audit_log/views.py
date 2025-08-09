# audit_log/views.py

from django.shortcuts import render
from django.contrib.auth.decorators import login_required, permission_required
from .models import RoleChangeLog

@login_required
# We use 'view_staffmember' permission as a proxy for manager-level access
@permission_required('staff.view_staffmember', raise_exception=True)
def role_change_log_view(request):
    """
    Displays a list of all role change events.
    """
    logs = RoleChangeLog.objects.select_related('actor', 'target_user').all()
    
    context = {
        'logs': logs,
        'page_title': 'Role Change Audit Log'
    }
    return render(request, 'audit_log/role_change_log.html', context)