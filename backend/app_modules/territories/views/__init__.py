# app_modules/territories/views/__init__.py
"""Views package for Territory module."""

from .views import TerritoryViewSet
from .views_bulk import TerritoryBulkViewSet

__all__ = [
    'TerritoryViewSet',
    'TerritoryBulkViewSet',
]