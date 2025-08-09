# audit_log/signals.py

from django.contrib.auth.models import User, Group
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from .models import RoleChangeLog
from .middleware import get_current_user

@receiver(m2m_changed, sender=User.groups.through)
def log_role_changes(sender, instance, action, reverse, model, pk_set, **kwargs):
    """
    A signal receiver that logs changes to a user's group memberships.
    """
    # We are only interested in the 'post_add' and 'post_remove' actions.
    if action not in ["post_add", "post_remove"]:
        return

    actor = get_current_user()
    # Do not log if the actor is anonymous or if the change is not initiated by a user.
    if not actor or actor.is_anonymous:
        return

    changed_groups = Group.objects.filter(pk__in=pk_set)
    role_names = ", ".join([group.name for group in changed_groups])

    if not role_names:
        return

    action_description = "Roles Added" if action == "post_add" else "Roles Removed"

    RoleChangeLog.objects.create(
        actor=actor,
        target_user=instance,
        action=action_description,
        roles_changed=role_names
    )