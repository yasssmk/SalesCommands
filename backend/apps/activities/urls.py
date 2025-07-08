from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views.activities_view import ActivityAPIView, ActivityChoicesView

app_name = 'activities'


urlpatterns = [
    # Activity CRUD operations
    path('', ActivityAPIView.as_view(), name='activity-list-create'),
    path('<int:pk>/', ActivityAPIView.as_view(), name='activity-detail'),
    
    # Custom activity actions
    path('<int:pk>/complete/', ActivityAPIView.as_view(), {'action': 'complete'}, name='activity-complete'),
    path('<int:pk>/increment_call_attempts/', ActivityAPIView.as_view(), {'action': 'increment_call_attempts'}, name='activity-increment-call-attempts'),
    
    # Activity collections
    path('my_activities/', ActivityAPIView.as_view(), {'action': 'my_activities'}, name='activity-my-activities'),
    path('overdue/', ActivityAPIView.as_view(), {'action': 'overdue'}, name='activity-overdue'),
    path('upcoming/', ActivityAPIView.as_view(), {'action': 'upcoming'}, name='activity-upcoming'),
    path('sequence_activities/', ActivityAPIView.as_view(), {'action': 'sequence_activities'}, name='activity-sequence-activities'),
    
    # Activity choices
    path('choices/', ActivityChoicesView.as_view(), name='activity-choices'),
]