# app_modules/bi/urls.py
"""
URL configuration for the BI module.

Follows the same lazy get_urlpatterns() pattern as the notifications module.
"""

from django.urls import path

app_name = 'module_bi'


# Lazy imports to avoid circular import at module load.
def get_urlpatterns():
    from .views import KPIDetailView, KPIBatchView

    return [
        # Batch MUST come before the <key> route so 'batch' is not captured as a key.
        path('kpi/batch/', KPIBatchView.as_view(), name='kpi-batch'),
        path('kpi/<str:key>/', KPIDetailView.as_view(), name='kpi-detail'),
    ]


urlpatterns = get_urlpatterns()
