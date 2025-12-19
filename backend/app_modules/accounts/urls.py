# app_modules/accounts/urls.py
"""
URL configuration for CompanyAccount module.

Follows the same patterns as end_users URLs.
"""

from django.urls import path

app_name = 'module_accounts'

# Lazy imports to avoid circular import
def get_urlpatterns():
    from .views import (
        CompanyAccountViewSet,
        CompanyAccountChoicesView,
        CompanyAccountBulkViewSet,
    )
    
    return [
        # =========================================================================
        # CHOICES - Must be before CRUD to avoid conflict with {id}
        # =========================================================================
        path('choices/', CompanyAccountChoicesView.as_view(), name='choices'),
        
        # =========================================================================
        # BULK OPERATIONS
        # =========================================================================
        path('bulk-create/', CompanyAccountBulkViewSet.as_view({
            'post': 'bulk_create'
        }), name='bulk-create'),
        
        path('bulk-update/', CompanyAccountBulkViewSet.as_view({
            'patch': 'bulk_update'
        }), name='bulk-update'),
        
        path('bulk-delete/', CompanyAccountBulkViewSet.as_view({
            'delete': 'bulk_delete'
        }), name='bulk-delete'),
        
        # =========================================================================
        # CRUD OPERATIONS
        # =========================================================================
        path('', CompanyAccountViewSet.as_view({
            'get': 'list',
            'post': 'create'
        }), name='list'),
        
        path('<uuid:pk>/', CompanyAccountViewSet.as_view({
            'get': 'retrieve',
            'put': 'update',
            'patch': 'partial_update',
            'delete': 'destroy'
        }), name='detail'),
        
        # =========================================================================
        # CUSTOM ACTIONS
        # =========================================================================
        path('<uuid:pk>/workspace/', CompanyAccountViewSet.as_view({
            'get': 'workspace'
        }), name='workspace'),
            
        path('<uuid:pk>/qualification/', CompanyAccountViewSet.as_view({
            'get': 'qualification'
        }), name='qualification'),
        
        path('<uuid:pk>/tech-stacks/', CompanyAccountViewSet.as_view({
            'get': 'tech_stacks'
        }), name='tech-stacks'),
        
        path('<uuid:pk>/hierarchy/', CompanyAccountViewSet.as_view({
            'get': 'hierarchy'
        }), name='hierarchy'),
    ]

urlpatterns = get_urlpatterns()