"""
Core URLs - Infrastructure endpoints

Contains endpoints for core infrastructure functionality:
- Operation status polling (for async bulk operations)

These endpoints are essential for the application and should NOT be removed.
"""
from django.urls import path

from core.views.operation_views import OperationStatusView

app_name = 'core'

urlpatterns = [
    # =========================================================================
    # OPERATION STATUS POLLING
    # =========================================================================
    # Used by frontend to poll status of long-running bulk operations
    # after client-side timeout. Works with idempotency system.
    #
    # Example: GET /core/operations/abc123-def456/status/
    # Returns: { "status": "running|succeeded|failed", "result": {...} }
    # =========================================================================
    path(
        'operations/<str:key>/status/',
        OperationStatusView.as_view(),
        name='operation-status'
    ),
]