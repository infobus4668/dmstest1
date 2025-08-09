# audit_log/models.py

from django.db import models
from django.conf import settings

class RoleChangeLog(models.Model):
    """
    A log entry that records a change in a user's group (role) assignments.
    """
    # The user who performed the action. Can be null if the user is deleted.
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='made_role_changes',
        help_text="The user who made the role change."
    )
    # The user whose roles were changed. If this user is deleted, their logs are also deleted.
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='role_changes_received',
        help_text="The user whose roles were changed."
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        help_text="The date and time the change occurred."
    )
    action = models.CharField(
        max_length=50,
        help_text="The action performed (e.g., 'Roles Added', 'Roles Removed')."
    )
    roles_changed = models.TextField(
        help_text="A list of the roles (groups) that were added or removed."
    )

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Role Change Log'
        verbose_name_plural = 'Role Change Logs'

    def __str__(self):
        return f"{self.actor} changed roles for {self.target_user} at {self.timestamp.strftime('%Y-%m-%d %H:%M')}"