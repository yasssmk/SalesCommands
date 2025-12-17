# app_modules/contacts/apps.py
"""
Django AppConfig for Contact module.
"""

from django.apps import AppConfig


class ContactsConfig(AppConfig):
    """Configuration for Contact module."""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app_modules.contacts'
    label = 'module_contacts'
    verbose_name = 'Contacts (Module)'