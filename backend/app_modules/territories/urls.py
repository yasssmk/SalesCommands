# backend/app_modules/territories/urls.py
"""
URL configuration for Territory module.

Follows the same patterns as app_modules/accounts/urls.py
"""

from django.urls import path

app_name = 'territories'


# Lazy imports to avoid circular import
def get_urlpatterns():
    from .views import TerritoryViewSet, TerritoryBulkViewSet
    
    return [
        # =========================================================================
        # CHOICES - Must be before CRUD to avoid conflict with {id}
        # =========================================================================
        path('choices/', TerritoryViewSet.as_view({
            'get': 'choices'
        }), name='choices'),
        
        # =========================================================================
        # BULK OPERATIONS
        # =========================================================================
        path('bulk-delete/', TerritoryBulkViewSet.as_view({
            'delete': 'bulk_delete'
        }), name='bulk-delete'),

        path('counts/', TerritoryBulkViewSet.as_view({
            'post': 'counts'
        }), name='counts'),

        # =========================================================================
        # CRUD OPERATIONS
        # =========================================================================
        path('', TerritoryViewSet.as_view({
            'get': 'list',
            'post': 'create'
        }), name='list'),
        
        path('<uuid:pk>/', TerritoryViewSet.as_view({
            'get': 'retrieve',
            'put': 'update',
            'patch': 'partial_update',
            'delete': 'destroy'
        }), name='detail'),
        
        # =========================================================================
        # CUSTOM ACTIONS
        # =========================================================================
        path('<uuid:pk>/accounts-count/', TerritoryViewSet.as_view({
            'get': 'accounts_count'
        }), name='accounts-count'),

        path('<uuid:pk>/workspace/', TerritoryViewSet.as_view({
            'get': 'workspace'
        }), name='workspace'),

    ]


urlpatterns = get_urlpatterns()