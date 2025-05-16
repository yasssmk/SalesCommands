# apps/campaign/urls.py
from django.urls import path
from .views.campaign_management_views import CampaignManagementViewSet, ActivityResultViewSet
from .views.campaign_views import CampaignViewSet
from .views.campaign_target_views import CampaignTargetViewSet
from .views.campaign_objective_views import CampaignObjectiveViewSet

urlpatterns = [
    
    # Campaign Management - Basic CRUD
    path('', CampaignManagementViewSet.as_view({'get': 'list', 'post': 'create'}), name='campaign-list'),
    path('<int:pk>/', CampaignManagementViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='campaign-detail'),
    
    # Campaign Creation with Targets
    path('create-with-targets/', CampaignManagementViewSet.as_view({'post': 'create_with_targets'}), name='campaign-create-with-targets'),
    
    # Campaign Control Actions
    path('<int:pk>/start/', CampaignManagementViewSet.as_view({'post': 'start_campaign'}), name='campaign-start'),
    path('<int:pk>/pause/', CampaignManagementViewSet.as_view({'post': 'pause_campaign'}), name='campaign-pause'),
    path('<int:pk>/resume/', CampaignManagementViewSet.as_view({'post': 'resume_campaign'}), name='campaign-resume'),
    
    # Campaign Information
    path('<int:pk>/playlist/', CampaignManagementViewSet.as_view({'get': 'playlist'}), name='campaign-playlist'),
    path('<int:pk>/summary/', CampaignManagementViewSet.as_view({'get': 'summary'}), name='campaign-summary'),
    path('<int:pk>/contacts-responses/', CampaignManagementViewSet.as_view({'get': 'contacts_with_responses'}), name='campaign-contacts-responses'),
    
    # Basic Campaign CRUD
    path('basic/', CampaignViewSet.as_view({'get': 'list', 'post': 'create'}), name='basic-campaign-list'),
    path('basic/<int:pk>/', CampaignViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='basic-campaign-detail'),
    path('basic/<int:pk>/summary/', CampaignViewSet.as_view({'get': 'summary'}), name='basic-campaign-summary'),
    
    # Campaign Targets
    path('targets/', CampaignTargetViewSet.as_view({'get': 'list', 'post': 'create'}), name='campaign-target-list'),
    path('targets/<int:pk>/', CampaignTargetViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='campaign-target-detail'),
    path('targets/<int:pk>/update-status/', CampaignTargetViewSet.as_view({'post': 'update_status'}), name='campaign-target-update-status'),
    path('targets/bulk-create/', CampaignTargetViewSet.as_view({'post': 'bulk_create'}), name='campaign-target-bulk-create'),
    
    # Campaign Objectives
    path('objectives/', CampaignObjectiveViewSet.as_view({'get': 'list', 'post': 'create'}), name='campaign-objective-list'),
    path('objectives/<int:pk>/', CampaignObjectiveViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='campaign-objective-detail'),
    path('objectives/<int:pk>/update-progress/', CampaignObjectiveViewSet.as_view({'post': 'update_progress'}), name='campaign-objective-update-progress'),
    
    # Activity Results
    path('activities/<int:pk>/complete/', ActivityResultViewSet.as_view({'post': 'complete_activity'}), name='activity-complete'),
    path('activities/<int:pk>/add-response/', ActivityResultViewSet.as_view({'post': 'add_email_response'}), name='activity-add-response'),
]