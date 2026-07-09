# app_modules/notifications/apps.py
"""
Django AppConfig for Notification module.
"""

from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    """Configuration for Notification module."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app_modules.notifications'
    label = 'module_notifications'
    verbose_name = 'Notifications (Module)'
