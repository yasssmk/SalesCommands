# app_modules/quotas/urls.py
"""URL configuration for the quotas module (scoped CRUD only)."""

from rest_framework.routers import DefaultRouter

from .views import QuotaViewSet

app_name = 'module_quotas'

router = DefaultRouter()
router.register(r'quotas', QuotaViewSet, basename='quota')

urlpatterns = router.urls
