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
        # Sprint « Cycle de vie des contacts », étape 2: an activity linked to
        # a decision cycle gives it to its signals. Imported WITHOUT a
        # try/except: a broken receiver must fail loudly, not silently skip.
        from app_modules.activities.signals import signal_cycle_attachment  # noqa: F401