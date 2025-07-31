# apps/opportunities/apps.py

from django.apps import AppConfig


class OpportunitiesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.opportunities'
    verbose_name = "Opportunities"
    
    def ready(self):
        """Register signals when app is ready"""
        from .signals import financial_signals