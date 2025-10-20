# backend/apps/ops/apps.py

"""
Operations Test App Configuration

Temporary app for testing timeout behavior and error handling.
Should be disabled/removed in production.
"""

from django.apps import AppConfig


class OpsConfig(AppConfig):
    """
    Configuration for the Operations Test app.
    
    This app provides test endpoints for:
    - Timeout validation (408)
    - Error handling (500, 404)
    - Retry logic testing
    
    ⚠️ WARNING: Only for development/staging. Disable in production.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.ops'
    verbose_name = 'Operations Test (Dev Only)'