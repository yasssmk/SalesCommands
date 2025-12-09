# backend/app_modules/territories/urls.py
"""
URL configuration for Territory module.

Follows the same patterns as app_modules/accounts/urls.py
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TerritoryViewSet

app_name = 'territories'

router = DefaultRouter()
router.register(r'', TerritoryViewSet, basename='territory')

urlpatterns = [
    path('', include(router.urls)),
]