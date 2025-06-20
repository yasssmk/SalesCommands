# apps/campaign/urls.py (version complète mise à jour)
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
    # CAMPAIGN ANALYTICS & DASHBOARD (SOURCE UNIQUE - NOUVEAUX ENDPOINTS)
    # =========================================================================
    
    # Dashboard complet (service analytics)
    path('<int:pk>/dashboard/', CampaignViewSet.as_view({'get': 'dashboard'}), name='campaign-dashboard'),
    
    # Dashboard rapide (helpers modèle)
    path('<int:pk>/dashboard-summary/', CampaignViewSet.as_view({'get': 'dashboard_summary'}), name='campaign-dashboard-summary'),
    
    # Analytics spécialisés
    path('<int:pk>/objectives-progress/', CampaignViewSet.as_view({'get': 'objectives_progress'}), name='campaign-objectives-progress'),
    path('<int:pk>/conversion-analysis/', CampaignViewSet.as_view({'get': 'conversion_analysis'}), name='campaign-conversion-analysis'),
    
    # Métriques simples et maintenance
    path('<int:pk>/metrics/', CampaignViewSet.as_view({'get': 'metrics'}), name='campaign-metrics'),
    path('<int:pk>/integrity-check/', CampaignViewSet.as_view({'post': 'integrity_check'}), name='campaign-integrity-check'),
    path('<int:pk>/cleanup-tracking/', CampaignViewSet.as_view({'post': 'cleanup_tracking'}), name='campaign-cleanup-tracking'),
    
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
    # BASIC CAMPAIGN CRUD (Interface alternative simplifiée)
    # =========================================================================
    
    path('basic/', CampaignViewSet.as_view({'get': 'list', 'post': 'create'}), name='basic-campaign-list'),
    path('basic/<int:pk>/', CampaignViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='basic-campaign-detail'),
    path('basic/<int:pk>/summary/', CampaignViewSet.as_view({'get': 'summary'}), name='basic-campaign-summary'),
    
    # =========================================================================
    # CAMPAIGN OBJECTIVES (CRUD UNIQUEMENT - PAS D'ANALYTICS)
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
    path('stakeholders/campaign/<int:campaign_id>/', CampaignStakeholderViewSet.as_view({'get': 'list'}), name='campaign-stakeholder-by-campaign'),
    
    # =========================================================================
    # ACTIVITY RESULTS & NEXT STEPS
    # =========================================================================
    
    path('activities/<int:pk>/complete/', ActivityResultViewSet.as_view({'post': 'complete_activity'}), name='activity-complete'),
    path('activities/<int:pk>/add-response/', ActivityResultViewSet.as_view({'post': 'add_email_response'}), name='activity-add-response'),
    path('activities/next-step-options/', ActivityResultViewSet.as_view({'get': 'get_next_step_options'}), name='activity-next-step-options'),
    path('activities/next-step-process/', ActivityResultViewSet.as_view({'post': 'process_next_step_choice'}), name='activity-next-step-process'),
]

# =========================================================================
# DOCUMENTATION DES ENDPOINTS PRINCIPAUX
# =========================================================================

"""
UNIFIED API ENDPOINTS (après consolidation) :

=== CAMPAIGN CRUD ===
GET    /campaigns/                          # List campaigns
POST   /campaigns/                          # Create campaign  
GET    /campaigns/{id}/                     # Get campaign details
PUT    /campaigns/{id}/                     # Update campaign
DELETE /campaigns/{id}/                     # Delete campaign

=== CAMPAIGN CREATION ===
POST   /campaigns/create_with_targets/      # Create campaign with targets & activities

=== CAMPAIGN LIFECYCLE ===
POST   /campaigns/{id}/start_campaign/      # Start campaign
POST   /campaigns/{id}/pause_campaign/      # Pause campaign  
POST   /campaigns/{id}/resume_campaign/     # Resume campaign

=== CAMPAIGN EXECUTION ===
GET    /campaigns/{id}/playlist/            # Get campaign playlist
GET    /campaigns/{id}/contacts_with_responses/  # Get contacts with responses
POST   /campaigns/{id}/add-manual-activity/ # Add manual activity

=== CAMPAIGN MANAGEMENT ===
POST   /campaigns/{id}/remove_account/      # Remove account from campaign
POST   /campaigns/{id}/remove_contact/      # Remove contact from campaign

=== CAMPAIGN ANALYTICS ===
GET    /campaigns/{id}/summary/             # Campaign summary (detailed)
GET    /campaigns/{id}/activities/          # All campaign activities
GET    /campaigns/{id}/account_activities/  # Activities for specific account
GET    /campaigns/{id}/contact_activities/  # Activities for specific contact

=== CAMPAIGN DASHBOARD ===
GET    /campaigns/{id}/dashboard/           # Full dashboard data
GET    /campaigns/{id}/dashboard_summary/   # Simple dashboard summary  
GET    /campaigns/{id}/metrics/             # Raw metrics only

=== CAMPAIGN UTILITIES ===
GET    /campaigns/account_campaigns/        # Campaigns for specific account

=== CAMPAIGN OBJECTIVES ===
GET    /campaign-objectives/               # List objectives
POST   /campaign-objectives/               # Create objective
GET    /campaign-objectives/{id}/          # Get objective
PUT    /campaign-objectives/{id}/          # Update objective  
DELETE /campaign-objectives/{id}/          # Delete objective
POST   /campaign-objectives/{id}/set_as_primary/  # Set as primary
POST   /campaign-objectives/{id}/sync_progress/   # Sync progress

=== CAMPAIGN STAKEHOLDERS ===
GET    /campaign-stakeholders/             # List stakeholders
POST   /campaign-stakeholders/             # Create stakeholder
GET    /campaign-stakeholders/{id}/        # Get stakeholder
PUT    /campaign-stakeholders/{id}/        # Update stakeholder
DELETE /campaign-stakeholders/{id}/        # Delete stakeholder
POST   /campaign-stakeholders/bulk-add/    # Bulk add stakeholders
POST   /campaign-stakeholders/bulk-remove/ # Bulk remove stakeholders

=== CAMPAIGN TARGETS ===  
GET    /campaign-targets/                  # List targets
POST   /campaign-targets/                  # Create target
GET    /campaign-targets/{id}/             # Get target
PUT    /campaign-targets/{id}/             # Update target
DELETE /campaign-targets/{id}/             # Delete target
POST   /campaign-targets/{id}/update_status/      # Update target status
POST   /campaign-targets/bulk_create/      # Bulk create targets

=== ACTIVITY RESULTS ===
POST   /activity-results/{id}/complete_activity/       # Complete activity
GET    /activity-results/get_next_step_options/        # Get next step options  
POST   /activity-results/process_next_step_choice/     # Process next step choice
POST   /activity-results/{id}/add_email_response/      # Add email response

=== QUERY PARAMETERS ===
?my_campaigns=true          # Filter to user's campaigns
?status=ACTIVE              # Filter by campaign status
?campaign_type=HUNTING      # Filter by campaign type
?sequence_type=CHASING      # Filter by sequence type
?owner=123                  # Filter by owner ID
?stakeholder_role=EXECUTOR  # Filter by stakeholder role
?start_after=2025-01-01     # Filter by start date after
?start_before=2025-12-31    # Filter by start date before
?limit=20                   # Limit results (for playlist, etc.)
?include=objectives,tracking # Dashboard sections to include
?format=summary|detailed    # Dashboard format type
"""