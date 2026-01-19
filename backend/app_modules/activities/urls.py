# app_modules/activities/urls.py
"""
URL configuration for Activity module.

Follows the same patterns as CompanyAccount and DecisionCycle URLs.
"""

from django.urls import path

app_name = 'module_activities'


def get_urlpatterns():
    """Lazy imports to avoid circular import."""
    from .views import ActivityViewSet, ActivityChoicesView
    
    return [
        # =====================================================================
        # CHOICES - Must be before CRUD to avoid conflict with {id}
        # =====================================================================
        path('choices/', ActivityChoicesView.as_view(), name='choices'),
        
        # =====================================================================
        # LIST ACTIONS
        # =====================================================================
        path('create-with-entities/', ActivityViewSet.as_view({
            'post': 'create_with_entities'
        }), name='create-with-entities'),
        
        path('my-activities/', ActivityViewSet.as_view({
            'get': 'my_activities'
        }), name='my-activities'),
        
        path('by-account/', ActivityViewSet.as_view({
            'get': 'by_account'
        }), name='by-account'),
        
        path('by-step/', ActivityViewSet.as_view({
            'get': 'by_step'
        }), name='by-step'),
        
        path('overdue/', ActivityViewSet.as_view({
            'get': 'overdue'
        }), name='overdue'),
        
        path('upcoming/', ActivityViewSet.as_view({
            'get': 'upcoming'
        }), name='upcoming'),
        
        # =====================================================================
        # CRUD OPERATIONS
        # =====================================================================
        path('', ActivityViewSet.as_view({
            'get': 'list',
            'post': 'create'
        }), name='list'),
        
        path('<uuid:pk>/', ActivityViewSet.as_view({
            'get': 'retrieve',
            'put': 'update',
            'patch': 'partial_update',
            'delete': 'destroy'
        }), name='detail'),
        
        # =====================================================================
        # INSTANCE ACTIONS
        # =====================================================================
        path('<uuid:pk>/complete/', ActivityViewSet.as_view({
            'post': 'complete'
        }), name='complete'),
        
        path('<uuid:pk>/cancel/', ActivityViewSet.as_view({
            'post': 'cancel'
        }), name='cancel'),
    ]


urlpatterns = get_urlpatterns()