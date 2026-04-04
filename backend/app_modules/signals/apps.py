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