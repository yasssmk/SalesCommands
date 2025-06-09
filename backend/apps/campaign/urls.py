# apps/campaign/urls.py
from django.urls import path
from .views.campaign_management_views import CampaignManagementViewSet, ActivityResultViewSet
from .views.campaign_views import CampaignViewSet
from .views.campaign_target_views import CampaignTargetViewSet
from .views.campaign_objective_views import CampaignObjectiveViewSet
from .views.campaign_stakeholder_views import CampaignStakeholderViewSet

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
    
    # NEW: Account/Contact Management
    path('account-campaigns/', CampaignManagementViewSet.as_view({'get': 'account_campaigns'}), name='account-campaigns'),
    path('<int:pk>/remove-account/', CampaignManagementViewSet.as_view({'post': 'remove_account'}), name='campaign-remove-account'),
    path('<int:pk>/remove-contact/', CampaignManagementViewSet.as_view({'post': 'remove_contact'}), name='campaign-remove-contact'),
    
    # NEW: Activity Listing
    path('<int:pk>/activities/', CampaignManagementViewSet.as_view({'get': 'activities'}), name='campaign-activities'),
    path('<int:pk>/account-activities/', CampaignManagementViewSet.as_view({'get': 'account_activities'}), name='campaign-account-activities'),
    path('<int:pk>/contact-activities/', CampaignManagementViewSet.as_view({'get': 'contact_activities'}), name='campaign-contact-activities'),
     path('<int:pk>/add-manual-activity/', CampaignManagementViewSet.as_view({'post': 'add_manual_activity'}), name='campaign-add-manual-activity'),
    
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

        # Campaign Stakeholders
    path('stakeholders/', CampaignStakeholderViewSet.as_view({'get': 'list', 'post': 'create'}), name='campaign-stakeholder-list'),
    path('stakeholders/<int:pk>/', CampaignStakeholderViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='campaign-stakeholder-detail'),
    path('stakeholders/bulk-add/', CampaignStakeholderViewSet.as_view({'post': 'bulk_add'}), name='campaign-stakeholder-bulk-add'),
    path('stakeholders/bulk-remove/', CampaignStakeholderViewSet.as_view({'post': 'bulk_remove'}), name='campaign-stakeholder-bulk-remove'),
    path('stakeholders/campaign/<int:campaign_id>/', CampaignStakeholderViewSet.as_view({'get': 'list'}), name='campaign-stakeholder-by-campaign'),
]