# apps/leads/urls.py

from django.urls import path
from apps.leads.views import LeadViewSet

app_name = 'leads'

urlpatterns = [
    # Lead Management - Basic CRUD
    path('', LeadViewSet.as_view({'get': 'list', 'post': 'create'}), name='lead-list'),
    path('<int:pk>/', LeadViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='lead-detail'),
    
    # Lead Actions
    path('<int:pk>/qualify/', LeadViewSet.as_view({'post': 'qualify'}), name='lead-qualify'),
    path('<int:pk>/disqualify/', LeadViewSet.as_view({'post': 'disqualify'}), name='lead-disqualify'),
    path('<int:pk>/convert/', LeadViewSet.as_view({'post': 'convert'}), name='lead-convert'),
    path('<int:pk>/assign/', LeadViewSet.as_view({'post': 'assign'}), name='lead-assign'),
    
    # Lead Activities
    path('<int:pk>/activities/', LeadViewSet.as_view({'get': 'activities'}), name='lead-activities'),
    path('<int:pk>/add-activity/', LeadViewSet.as_view({'post': 'add_activity'}), name='lead-add-activity'),
    path('<int:pk>/remove-activity/', LeadViewSet.as_view({'post': 'remove_activity'}), name='lead-remove-activity'),
    
    # Lead Information
    path('summary/', LeadViewSet.as_view({'get': 'summary'}), name='lead-summary'),
]