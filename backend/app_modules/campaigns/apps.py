# app_modules/campaigns/apps.py
"""
Django AppConfig for Campaign module.
"""

from django.apps import AppConfig


class CampaignsConfig(AppConfig):
    """Configuration for Campaign module."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app_modules.campaigns'
    label = 'module_campaigns'
    verbose_name = 'Campaigns Module'

    def ready(self):
        """Register campaign signals when app is ready."""
        try:
            from app_modules.campaigns.signals import signals  # noqa: F401
        except ImportError as e:
            print(f"[CAMPAIGNS] Warning: Could not load signals: {e}")
        except Exception as e:
            print(f"[CAMPAIGNS] Error loading signals: {e}")