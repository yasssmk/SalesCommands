# apps/campaign/urls.py (version corrigée et nettoyée)
from django.urls import path
from .views.campaign_views import CampaignViewSet, ActivityResultViewSet
from .views.campaign_target_views import CampaignTargetViewSet
from .views.campaign_objective_views import CampaignObjectiveViewSet
from .views.campaign_stakeholder_views import CampaignStakeholderViewSet

urlpatterns = [
    
    # =========================================================================
    # CAMPAIGN MANAGEMENT - PRINCIPAL (Source unique pour dashboard + gestion)
    # =========================================================================
    
    # Basic CRUD
    path('', CampaignViewSet.as_view({'get': 'list', 'post': 'create'}), name='campaign-list'),
    path('<int:pk>/', CampaignViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='campaign-detail'),
    
    # Campaign Creation with Targets
    path('create-with-targets/', CampaignViewSet.as_view({'post': 'create_with_targets'}), name='campaign-create-with-targets'),
    
    # Campaign Control Actions
    path('<int:pk>/start/', CampaignViewSet.as_view({'post': 'start_campaign'}), name='campaign-start'),
    path('<int:pk>/pause/', CampaignViewSet.as_view({'post': 'pause_campaign'}), name='campaign-pause'),
    path('<int:pk>/resume/', CampaignViewSet.as_view({'post': 'resume_campaign'}), name='campaign-resume'),
    
    # Campaign Playlist & Summary
    path('<int:pk>/playlist/', CampaignViewSet.as_view({'get': 'playlist'}), name='campaign-playlist'),
    path('<int:pk>/summary/', CampaignViewSet.as_view({'get': 'summary'}), name='campaign-summary'),
    path('<int:pk>/contacts-responses/', CampaignViewSet.as_view({'get': 'contacts_with_responses'}), name='campaign-contacts-responses'),
    
    # =========================================================================
    # CAMPAIGN DASHBOARD UNIFIÉ (après consolidation étape 2.1)
    # =========================================================================
    
    # Dashboard unifié configurable (remplace dashboard_summary, metrics, objectives_progress, conversion_analysis)
    path('<int:pk>/dashboard/', CampaignViewSet.as_view({'get': 'dashboard'}), name='campaign-dashboard'),
    
    # =========================================================================
    # ACCOUNT/CONTACT MANAGEMENT
    # =========================================================================
    
    path('account-campaigns/', CampaignViewSet.as_view({'get': 'account_campaigns'}), name='account-campaigns'),
    path('<int:pk>/remove-account/', CampaignViewSet.as_view({'post': 'remove_account'}), name='campaign-remove-account'),
    path('<int:pk>/remove-contact/', CampaignViewSet.as_view({'post': 'remove_contact'}), name='campaign-remove-contact'),
    
    # =========================================================================
    # ACTIVITY MANAGEMENT
    # =========================================================================
    
    path('<int:pk>/activities/', CampaignViewSet.as_view({'get': 'activities'}), name='campaign-activities'),
    path('<int:pk>/account-activities/', CampaignViewSet.as_view({'get': 'account_activities'}), name='campaign-account-activities'),
    path('<int:pk>/contact-activities/', CampaignViewSet.as_view({'get': 'contact_activities'}), name='campaign-contact-activities'),
    path('<int:pk>/add-manual-activity/', CampaignViewSet.as_view({'post': 'add_manual_activity'}), name='campaign-add-manual-activity'),
    
    # =========================================================================
    # CAMPAIGN OBJECTIVES (CRUD UNIQUEMENT)
    # =========================================================================
    
    path('objectives/', CampaignObjectiveViewSet.as_view({'get': 'list', 'post': 'create'}), name='campaign-objective-list'),
    path('objectives/<int:pk>/', CampaignObjectiveViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='campaign-objective-detail'),
    
    # Gestion spécifique aux objectifs (CRUD avancé)
    path('objectives/<int:pk>/set-as-primary/', CampaignObjectiveViewSet.as_view({'post': 'set_as_primary'}), name='campaign-objective-set-primary'),
    path('objectives/<int:pk>/sync-progress/', CampaignObjectiveViewSet.as_view({'post': 'sync_progress'}), name='campaign-objective-sync-progress'),
    
    # =========================================================================
    # CAMPAIGN TARGETS (CRUD)
    # =========================================================================
    
    path('targets/', CampaignTargetViewSet.as_view({'get': 'list', 'post': 'create'}), name='campaign-target-list'),
    path('targets/<int:pk>/', CampaignTargetViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='campaign-target-detail'),
    path('targets/<int:pk>/update-status/', CampaignTargetViewSet.as_view({'post': 'update_status'}), name='campaign-target-update-status'),
    path('targets/bulk-create/', CampaignTargetViewSet.as_view({'post': 'bulk_create'}), name='campaign-target-bulk-create'),
    
    # =========================================================================
    # CAMPAIGN STAKEHOLDERS (CRUD)
    # =========================================================================
    
    path('stakeholders/', CampaignStakeholderViewSet.as_view({'get': 'list', 'post': 'create'}), name='campaign-stakeholder-list'),
    path('stakeholders/<int:pk>/', CampaignStakeholderViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='campaign-stakeholder-detail'),
    path('stakeholders/bulk-add/', CampaignStakeholderViewSet.as_view({'post': 'bulk_add'}), name='campaign-stakeholder-bulk-add'),
    path('stakeholders/bulk-remove/', CampaignStakeholderViewSet.as_view({'post': 'bulk_remove'}), name='campaign-stakeholder-bulk-remove'),
    
    # =========================================================================
    # ACTIVITY RESULTS & NEXT STEPS
    # =========================================================================
    
    path('activities/<int:pk>/complete/', ActivityResultViewSet.as_view({'post': 'complete_activity'}), name='activity-complete'),
    path('activities/<int:pk>/add-response/', ActivityResultViewSet.as_view({'post': 'add_email_response'}), name='activity-add-response'),
    path('activities/next-step-options/', ActivityResultViewSet.as_view({'get': 'get_next_step_options'}), name='activity-next-step-options'),
    path('activities/next-step-process/', ActivityResultViewSet.as_view({'post': 'process_next_step_choice'}), name='activity-next-step-process'),
]

# =========================================================================
# DOCUMENTATION DES ENDPOINTS FINAUX (après nettoyage)
# =========================================================================

"""
ENDPOINTS VALIDÉS ET FONCTIONNELS :

=== CAMPAIGN CRUD ===
GET    /campaigns/                          # List campaigns
POST   /campaigns/                          # Create campaign  
GET    /campaigns/{id}/                     # Get campaign details
PUT    /campaigns/{id}/                     # Update campaign
DELETE /campaigns/{id}/                     # Delete campaign

=== CAMPAIGN CREATION ===
POST   /campaigns/create-with-targets/      # Create campaign with targets & activities

=== CAMPAIGN LIFECYCLE ===
POST   /campaigns/{id}/start/               # Start campaign
POST   /campaigns/{id}/pause/               # Pause campaign  
POST   /campaigns/{id}/resume/              # Resume campaign

=== CAMPAIGN EXECUTION ===
GET    /campaigns/{id}/playlist/            # Get campaign playlist
GET    /campaigns/{id}/contacts-responses/  # Get contacts with responses
POST   /campaigns/{id}/add-manual-activity/ # Add manual activity

=== CAMPAIGN MANAGEMENT ===
POST   /campaigns/{id}/remove-account/      # Remove account from campaign
POST   /campaigns/{id}/remove-contact/      # Remove contact from campaign

=== CAMPAIGN ANALYTICS ===
GET    /campaigns/{id}/summary/             # Campaign summary (detailed)
GET    /campaigns/{id}/activities/          # All campaign activities
GET    /campaigns/{id}/account-activities/  # Activities for specific account
GET    /campaigns/{id}/contact-activities/  # Activities for specific contact

=== CAMPAIGN DASHBOARD UNIFIÉ ===
GET    /campaigns/{id}/dashboard/           # Configurable dashboard
   ?include=objectives,tracking,activities   # Sections to include
   ?format=detailed|summary                  # Format type

=== CAMPAIGN UTILITIES ===
GET    /campaigns/account-campaigns/        # Campaigns for specific account

=== CAMPAIGN OBJECTIVES ===
GET    /campaigns/objectives/               # List objectives
POST   /campaigns/objectives/               # Create objective
GET    /campaigns/objectives/{id}/          # Get objective
PUT    /campaigns/objectives/{id}/          # Update objective  
DELETE /campaigns/objectives/{id}/          # Delete objective
POST   /campaigns/objectives/{id}/set-as-primary/  # Set as primary
POST   /campaigns/objectives/{id}/sync-progress/   # Sync progress

=== CAMPAIGN STAKEHOLDERS ===
GET    /campaigns/stakeholders/             # List stakeholders
POST   /campaigns/stakeholders/             # Create stakeholder
GET    /campaigns/stakeholders/{id}/        # Get stakeholder
PUT    /campaigns/stakeholders/{id}/        # Update stakeholder
DELETE /campaigns/stakeholders/{id}/        # Delete stakeholder
POST   /campaigns/stakeholders/bulk-add/    # Bulk add stakeholders
POST   /campaigns/stakeholders/bulk-remove/ # Bulk remove stakeholders

=== CAMPAIGN TARGETS ===  
GET    /campaigns/targets/                  # List targets
POST   /campaigns/targets/                  # Create target
GET    /campaigns/targets/{id}/             # Get target
PUT    /campaigns/targets/{id}/             # Update target
DELETE /campaigns/targets/{id}/             # Delete target
POST   /campaigns/targets/{id}/update-status/      # Update target status
POST   /campaigns/targets/bulk-create/      # Bulk create targets

=== ACTIVITY RESULTS ===
POST   /campaigns/activities/{id}/complete/         # Complete activity
GET    /campaigns/activities/next-step-options/     # Get next step options  
POST   /campaigns/activities/next-step-process/     # Process next step choice
POST   /campaigns/activities/{id}/add-response/     # Add email response
"""