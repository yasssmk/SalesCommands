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