# staff/apps.py

from django.apps import AppConfig

class StaffConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'staff'

    def ready(self):
        """
        Import signals when the app is ready.
        """
        import staff.signals