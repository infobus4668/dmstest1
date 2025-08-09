# DENTALCLINICSYSTEM/staff/admin.py

from django.contrib import admin
from .models import StaffMember

@admin.register(StaffMember)
class StaffMemberAdmin(admin.ModelAdmin):
    """
    Admin configuration for the StaffMember model.
    """
    
    # Custom methods for the list display
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'Email'

    def get_user_groups(self, obj):
        if obj.user:
            return ", ".join([group.name for group in obj.user.groups.all()])
        return "N/A"
    get_user_groups.short_description = 'Roles (Groups)'

    # Configuration for the admin list view
    list_display = (
        'name',
        'user_email',
        'contact_number',
        'get_user_groups',
        'is_active',
        'date_joined',
    )

    list_filter = (
        'is_active',
        'user__groups',
        'date_joined',
    )
    
    list_editable = ('is_active',)

    search_fields = (
        'user__first_name',
        'user__last_name',
        'user__email',
        'contact_number',
        'user__username',
    )

    # Improves performance for user selection
    raw_id_fields = ('user',)
    
    ordering = ('-user__date_joined',)