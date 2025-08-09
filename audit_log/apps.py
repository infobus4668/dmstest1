# audit_log/apps.py

from django.apps import AppConfig

class AuditLogConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'audit_log'

    def ready(self):
        # Import signals to ensure they are connected when the app is ready.
        import audit_log.signals