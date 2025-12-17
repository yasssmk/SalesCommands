# app_modules/contacts/urls.py
"""
URL configuration for Contact module.

Follows the same patterns as CompanyAccount URLs.
"""

from django.urls import path

app_name = 'module_contacts'


# Lazy imports to avoid circular import
def get_urlpatterns():
    from .views import (
        ContactViewSet,
        ContactChoicesView,
        ContactBulkViewSet,
    )
    
    return [
        # =========================================================================
        # CHOICES - Must be before CRUD to avoid conflict with {id}
        # =========================================================================
        path('choices/', ContactChoicesView.as_view(), name='choices'),
        
        # =========================================================================
        # BULK OPERATIONS
        # =========================================================================
        path('bulk-create/', ContactBulkViewSet.as_view({
            'post': 'bulk_create'
        }), name='bulk-create'),
        
        path('bulk-update/', ContactBulkViewSet.as_view({
            'patch': 'bulk_update'
        }), name='bulk-update'),
        
        path('bulk-delete/', ContactBulkViewSet.as_view({
            'delete': 'bulk_delete'
        }), name='bulk-delete'),
        
        # =========================================================================
        # CRUD OPERATIONS
        # =========================================================================
        path('', ContactViewSet.as_view({
            'get': 'list',
            'post': 'create'
        }), name='list'),
        
        path('<uuid:pk>/', ContactViewSet.as_view({
            'get': 'retrieve',
            'put': 'update',
            'patch': 'partial_update',
            'delete': 'destroy'
        }), name='detail'),
        
        # =========================================================================
        # CUSTOM ACTIONS
        # =========================================================================
        path('<uuid:pk>/mark-email-invalid/', ContactViewSet.as_view({
            'post': 'mark_email_invalid'
        }), name='mark-email-invalid'),
        
        path('<uuid:pk>/mark-phone-invalid/', ContactViewSet.as_view({
            'post': 'mark_phone_invalid'
        }), name='mark-phone-invalid'),
        
        path('<uuid:pk>/mark-opted-out/', ContactViewSet.as_view({
            'post': 'mark_opted_out'
        }), name='mark-opted-out'),
    ]


urlpatterns = get_urlpatterns()