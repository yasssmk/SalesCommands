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