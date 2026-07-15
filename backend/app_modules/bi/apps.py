# app_modules/bi/apps.py
"""
Django AppConfig for the BI aggregation foundation.
"""

from django.apps import AppConfig


class BIConfig(AppConfig):
    """Configuration for the BI foundation module (KPI registry +, later,
    the compute/cache layer). Has no models of its own — it aggregates over
    the other modules' data."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app_modules.bi'
    label = 'module_bi'
    verbose_name = 'BI Foundation (Module)'

    def ready(self):
        # Register the declared KPIs, then wire the registry-driven cache
        # invalidation for their source models.
        from .definitions import load_all
        load_all()
        from .signals.cache_invalidation import connect_invalidation_receivers
        connect_invalidation_receivers()
