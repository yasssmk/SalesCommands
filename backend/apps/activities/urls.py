from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views.activities_view import ActivityViewSet, ActivityChoicesView

app_name = 'activities'

urlpatterns = [
    # Activity CRUD operations
    path('', ActivityViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='activity-list-create'),
    
    path('<int:pk>/', ActivityViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='activity-detail'),
    
    # Custom activity actions
    path('<int:pk>/complete/', ActivityViewSet.as_view({
        'post': 'complete'
    }), name='activity-complete'),
    
    path('<int:pk>/increment-call-attempts/', ActivityViewSet.as_view({
        'post': 'increment_call_attempts'
    }), name='activity-increment-call-attempts'),
    
    # Activity collections
    path('my-activities/', ActivityViewSet.as_view({
        'get': 'my_activities'
    }), name='activity-my-activities'),
    
    path('overdue/', ActivityViewSet.as_view({
        'get': 'overdue'
    }), name='activity-overdue'),
    
    path('upcoming/', ActivityViewSet.as_view({
        'get': 'upcoming'
    }), name='activity-upcoming'),
    
    path('sequence-activities/', ActivityViewSet.as_view({
        'get': 'sequence_activities'
    }), name='activity-sequence-activities'),
    
    # Activity choices
    path('choices/', ActivityChoicesView.as_view(), name='activity-choices'),
]