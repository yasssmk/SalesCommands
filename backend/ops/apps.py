# backend/ops/apps.py

"""
Ops App Configuration
"""

from django.apps import AppConfig


class OpsConfig(AppConfig):
    """
    Configuration for the Ops app.
    
    Provides testing and monitoring utilities for development.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ops'
    verbose_name = 'Operations & Testing'