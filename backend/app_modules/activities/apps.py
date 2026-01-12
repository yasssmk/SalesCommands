# app_modules/activities/apps.py
"""
App configuration for Activities module.
"""

from django.apps import AppConfig


class ActivitiesConfig(AppConfig):
    """Configuration for the Activities app."""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app_modules.activities'
    label = 'module_activities'
    verbose_name = 'Activities'
    
    def ready(self):
        """Import signals when app is ready."""
        pass  # Signals will be added later if needed