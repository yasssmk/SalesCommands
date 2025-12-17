# app_modules/contacts/views/__init__.py
"""Views package for Contact module."""

from .views import ContactViewSet, ContactChoicesView
from .views_bulk import ContactBulkViewSet

__all__ = [
    'ContactViewSet',
    'ContactChoicesView',
    'ContactBulkViewSet',
]