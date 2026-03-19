# app_modules/campaigns/apps.py
"""
Django AppConfig for Campaign module.
"""

import logging

from django.apps import AppConfig

logger = logging.getLogger('app_modules.campaigns')


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
            logger.warning("campaigns_signals_import_failed", exc_info=e)
        except Exception as e:
            logger.error("campaigns_signals_load_error", exc_info=e)