# backend/app_modules/signals/apps.py
"""
Django AppConfig for the Signals module.

name  = Python import path used in INSTALLED_APPS
label = unique Django app label (avoids collision with legacy apps.signals)
"""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class SignalsConfig(AppConfig):
    """AppConfig for app_modules.signals."""

    name = 'app_modules.signals'
    label = 'module_signals'
    verbose_name = _('Signals')
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        """Register cache invalidation signals when app is ready."""
        try:
            from app_modules.signals.signals import cache_invalidation  # noqa: F401
        except ImportError as e:
            import logging
            logging.getLogger('app_modules.signals').warning(
                "signals_cache_invalidation_import_failed", exc_info=e
            )