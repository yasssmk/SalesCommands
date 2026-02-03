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
        try:
            from app_modules.activities.signals import cache_invalidation  # noqa: F401
            print("[ACTIVITIES] Cache invalidation signals loaded successfully")
        except ImportError as e:
            print(f"[ACTIVITIES] Warning: Could not load cache signals: {e}")
        except Exception as e:
            print(f"[ACTIVITIES] Error loading signals: {e}")