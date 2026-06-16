# app_modules/decision_cycles/urls.py
"""
URL configuration for Decision Cycle module.

Follows the same patterns as CompanyAccount URLs.
"""

from django.urls import path

app_name = 'decision_cycles'


def get_urlpatterns():
    """Lazy imports to avoid circular import."""
    from .views import (
        DecisionCycleViewSet,
        DecisionStepViewSet,
        DecisionCycleChoicesView,
        DealProductViewSet,
        DealHealthSnapshotViewSet,
        ManagerNoteViewSet,
    )

    return [
        # =====================================================================
        # CHOICES - Must be before CRUD to avoid conflict with {id}
        # =====================================================================
        path('choices/', DecisionCycleChoicesView.as_view(), name='choices'),

        # =====================================================================
        # DECISION CYCLES - CRUD
        # =====================================================================
        path('', DecisionCycleViewSet.as_view({
            'get': 'list',
            'post': 'create'
        }), name='cycle-list'),

        path('<uuid:pk>/', DecisionCycleViewSet.as_view({
            'get': 'retrieve',
            'put': 'update',
            'patch': 'partial_update',
            'delete': 'destroy'
        }), name='cycle-detail'),

        # =====================================================================
        # DECISION CYCLES - CUSTOM ACTIONS
        # =====================================================================
        path('by-account/<uuid:account_id>/', DecisionCycleViewSet.as_view({
            'get': 'by_account'
        }), name='cycles-by-account'),

        path('<uuid:pk>/close/', DecisionCycleViewSet.as_view({
            'post': 'close'
        }), name='cycle-close'),

        path('<uuid:pk>/reopen/', DecisionCycleViewSet.as_view({
            'post': 'reopen'
        }), name='cycle-reopen'),

        path('<uuid:pk>/people/', DecisionCycleViewSet.as_view({
            'get': 'people'
        }), name='cycle-people'),

        path('<uuid:pk>/readiness/', DecisionCycleViewSet.as_view({
            'get': 'readiness'
        }), name='cycle-readiness'),

        # =====================================================================
        # DEAL PRODUCTS — nested under a cycle
        # =====================================================================
        path('<uuid:cycle_id>/products/', DealProductViewSet.as_view({
            'get': 'list',
            'post': 'create',
        }), name='deal-product-list'),

        path('<uuid:cycle_id>/products/<uuid:pk>/', DealProductViewSet.as_view({
            'get': 'retrieve',
            'patch': 'partial_update',
            'put': 'update',
            'delete': 'destroy',
        }), name='deal-product-detail'),

        # =====================================================================
        # DEAL HEALTH SNAPSHOTS — nested under a cycle (read-only)
        # =====================================================================
        path('<uuid:cycle_id>/health-snapshots/', DealHealthSnapshotViewSet.as_view({
            'get': 'list',
        }), name='deal-health-snapshot-list'),

        path('<uuid:cycle_id>/health-snapshots/latest/', DealHealthSnapshotViewSet.as_view({
            'get': 'latest',
        }), name='deal-health-snapshot-latest'),

        path('<uuid:cycle_id>/health-snapshots/<uuid:pk>/', DealHealthSnapshotViewSet.as_view({
            'get': 'retrieve',
        }), name='deal-health-snapshot-detail'),

        # =====================================================================
        # MANAGER NOTES — nested under a cycle
        # =====================================================================
        path('<uuid:cycle_id>/notes/', ManagerNoteViewSet.as_view({
            'get': 'list',
            'post': 'create',
        }), name='manager-note-list'),

        path('<uuid:cycle_id>/notes/<uuid:pk>/', ManagerNoteViewSet.as_view({
            'get': 'retrieve',
            'delete': 'destroy',
        }), name='manager-note-detail'),

        # =====================================================================
        # DECISION STEPS - CRUD
        # =====================================================================
        path('steps/', DecisionStepViewSet.as_view({
            'get': 'list',
            'post': 'create'
        }), name='step-list'),

        path('steps/<uuid:pk>/', DecisionStepViewSet.as_view({
            'get': 'retrieve',
            'put': 'update',
            'patch': 'partial_update',
            'delete': 'destroy'
        }), name='step-detail'),

        # =====================================================================
        # DECISION STEPS - CUSTOM ACTIONS
        # =====================================================================
        path('steps/<uuid:pk>/status/', DecisionStepViewSet.as_view({
            'patch': 'update_status'
        }), name='step-status'),
    ]


urlpatterns = get_urlpatterns()