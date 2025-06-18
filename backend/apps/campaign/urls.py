# apps/campaign/urls.py (version mise à jour)
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
    
    # Campaign Information & Analytics
    path('<int:pk>/playlist/', CampaignManagementViewSet.as_view({'get': 'playlist'}), name='campaign-playlist'),
    path('<int:pk>/summary/', CampaignManagementViewSet.as_view({'get': 'summary'}), name='campaign-summary'),
    path('<int:pk>/contacts-responses/', CampaignManagementViewSet.as_view({'get': 'contacts_with_responses'}), name='campaign-contacts-responses'),
    
    # === NOUVEAUX ENDPOINTS DASHBOARD & METRICS ===
    path('<int:pk>/dashboard/', CampaignManagementViewSet.as_view({'get': 'dashboard'}), name='campaign-dashboard'),
    path('<int:pk>/metrics/', CampaignManagementViewSet.as_view({'get': 'metrics'}), name='campaign-metrics'),
    path('<int:pk>/integrity-check/', CampaignManagementViewSet.as_view({'post': 'integrity_check'}), name='campaign-integrity-check'),
    path('<int:pk>/cleanup-tracking/', CampaignManagementViewSet.as_view({'post': 'cleanup_tracking'}), name='campaign-cleanup-tracking'),
    
    # Account/Contact Management
    path('account-campaigns/', CampaignManagementViewSet.as_view({'get': 'account_campaigns'}), name='account-campaigns'),
    path('<int:pk>/remove-account/', CampaignManagementViewSet.as_view({'post': 'remove_account'}), name='campaign-remove-account'),
    path('<int:pk>/remove-contact/', CampaignManagementViewSet.as_view({'post': 'remove_contact'}), name='campaign-remove-contact'),
    
    # Activity Listing and Management
    path('<int:pk>/activities/', CampaignManagementViewSet.as_view({'get': 'activities'}), name='campaign-activities'),
    path('<int:pk>/account-activities/', CampaignManagementViewSet.as_view({'get': 'account_activities'}), name='campaign-account-activities'),
    path('<int:pk>/contact-activities/', CampaignManagementViewSet.as_view({'get': 'contact_activities'}), name='campaign-contact-activities'),
    path('<int:pk>/add-manual-activity/', CampaignManagementViewSet.as_view({'post': 'add_manual_activity'}), name='campaign-add-manual-activity'),
    
    # Basic Campaign CRUD (Alternative interface)
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
    
    # Campaign Stakeholders
    path('stakeholders/', CampaignStakeholderViewSet.as_view({'get': 'list', 'post': 'create'}), name='campaign-stakeholder-list'),
    path('stakeholders/<int:pk>/', CampaignStakeholderViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='campaign-stakeholder-detail'),
    path('stakeholders/bulk-add/', CampaignStakeholderViewSet.as_view({'post': 'bulk_add'}), name='campaign-stakeholder-bulk-add'),
    path('stakeholders/bulk-remove/', CampaignStakeholderViewSet.as_view({'post': 'bulk_remove'}), name='campaign-stakeholder-bulk-remove'),
    path('stakeholders/campaign/<int:campaign_id>/', CampaignStakeholderViewSet.as_view({'get': 'list'}), name='campaign-stakeholder-by-campaign'),
    
    # Activity Results
    path('activities/<int:pk>/complete/', ActivityResultViewSet.as_view({'post': 'complete_activity'}), name='activity-complete'),
    path('activities/<int:pk>/add-response/', ActivityResultViewSet.as_view({'post': 'add_email_response'}), name='activity-add-response'),
    path('activities/next-step-options/', ActivityResultViewSet.as_view({'get': 'get_next_step_options'}), name='activity-next-step-options'),
]

# For reference, here are the key endpoints now available with standardized responses:

"""
CAMPAIGN MANAGEMENT ENDPOINTS (CampaignManagementViewSet):
POST   /campaigns/create-with-targets/                - Create campaign with targets and activities
POST   /campaigns/{id}/start/                         - Start/activate a campaign
GET    /campaigns/{id}/playlist/                      - Get campaign playlist (activities or contacts)
GET    /campaigns/{id}/summary/                       - Get comprehensive campaign summary
POST   /campaigns/{id}/pause/                         - Pause a campaign
POST   /campaigns/{id}/resume/                        - Resume a paused campaign
GET    /campaigns/{id}/contacts-responses/            - Get contacts with email/LinkedIn responses

=== NOUVEAUX ENDPOINTS DASHBOARD & METRICS (MVP) ===
GET    /campaigns/{id}/dashboard/                     - 🆕 Campaign dashboard avec objectifs vs réalisé + santé
GET    /campaigns/{id}/metrics/                       - 🆕 Métriques brutes simples
POST   /campaigns/{id}/integrity-check/               - 🆕 Vérification intégrité des données trackées
POST   /campaigns/{id}/cleanup-tracking/              - 🆕 Nettoyage données invalides (owners only)

ACCOUNT/CONTACT MANAGEMENT:
GET    /campaigns/account-campaigns/                  - Get campaigns for a specific account
POST   /campaigns/{id}/remove-account/                - Remove account from campaign
POST   /campaigns/{id}/remove-contact/                - Remove contact from campaign

ACTIVITY MANAGEMENT:
GET    /campaigns/{id}/activities/                    - Get all campaign activities
GET    /campaigns/{id}/account-activities/            - Get activities for specific account
GET    /campaigns/{id}/contact-activities/            - Get activities for specific contact
POST   /campaigns/{id}/add-manual-activity/           - Add manual activity for non-sequence campaigns

BASIC CAMPAIGN CRUD (CampaignViewSet):
GET    /campaigns/basic/                              - List campaigns with filters
POST   /campaigns/basic/                              - Create new campaign
GET    /campaigns/basic/{id}/                         - Get specific campaign
PUT    /campaigns/basic/{id}/                         - Update campaign
DELETE /campaigns/basic/{id}/                         - Delete campaign
GET    /campaigns/basic/{id}/summary/                 - Get campaign summary with objectives

CAMPAIGN OBJECTIVES (CampaignObjectiveViewSet):
GET    /campaigns/objectives/                         - List campaign objectives
POST   /campaigns/objectives/                         - Create new objective
GET    /campaigns/objectives/{id}/                    - Get specific objective
PUT    /campaigns/objectives/{id}/                    - Update objective
DELETE /campaigns/objectives/{id}/                    - Delete objective
POST   /campaigns/objectives/{id}/update-progress/   - Update objective progress

CAMPAIGN STAKEHOLDERS (CampaignStakeholderViewSet):
GET    /campaigns/stakeholders/                       - List campaign stakeholders
POST   /campaigns/stakeholders/                       - Create new stakeholder
GET    /campaigns/stakeholders/{id}/                  - Get specific stakeholder
PUT    /campaigns/stakeholders/{id}/                  - Update stakeholder
DELETE /campaigns/stakeholders/{id}/                  - Delete stakeholder
POST   /campaigns/stakeholders/bulk-add/              - Add multiple stakeholders
POST   /campaigns/stakeholders/bulk-remove/           - Remove multiple stakeholders

CAMPAIGN TARGETS (CampaignTargetViewSet):
GET    /campaigns/targets/                            - List campaign targets
POST   /campaigns/targets/                            - Create new target
GET    /campaigns/targets/{id}/                       - Get specific target
PUT    /campaigns/targets/{id}/                       - Update target
DELETE /campaigns/targets/{id}/                       - Delete target
POST   /campaigns/targets/{id}/update-status/         - Update target status
POST   /campaigns/targets/bulk-create/                - Create multiple targets

ACTIVITY RESULTS (ActivityResultViewSet):
POST   /campaigns/activities/{id}/complete/           - Complete activity with result
POST   /campaigns/activities/{id}/add-response/       - Add response to email/LinkedIn activity
GET    /campaigns/activities/next-step-options/       - Get available next step options

=== NOUVEAUX ENDPOINTS DASHBOARD - EXEMPLES D'UTILISATION ===

# Dashboard complet avec métriques vs objectifs
GET /campaigns/123/dashboard/
Response: {
  "success": true,
  "message": "Dashboard data retrieved for campaign 'Q1 Outreach'",
  "data": {
    "campaign": {...},
    "current_metrics": {
      "leads_created": 45,
      "meetings_secured": 12,
      "opportunities_created": 8,
      "deals_closed": 3,
      "pipeline_value": 125000.00,
      "revenue_generated": 45000.00
    },
    "objectives": [
      {
        "name": "Generate 50 leads",
        "type": "LEADS",
        "target_value": 50,
        "current_value": 45,
        "progress_percentage": 90.0,
        "status": "in_progress"
      }
    ],
    "health_indicators": {
      "overall_health": "good",
      "conversion_rates": {
        "leads_to_meetings": 26.7
      },
      "alerts": []
    }
  }
}

# Métriques simples
GET /campaigns/123/metrics/
Response: {
  "success": true,
  "message": "Metrics retrieved for campaign 'Q1 Outreach'",
  "data": {
    "campaign_id": 123,
    "campaign_name": "Q1 Outreach",
    "leads_created": 45,
    "meetings_secured": 12,
    "opportunities_created": 8,
    "deals_closed": 3,
    "pipeline_value": 125000.00,
    "revenue_generated": 45000.00
  }
}

# Vérification intégrité
POST /campaigns/123/integrity-check/
Response: {
  "success": true,
  "message": "Integrity check completed for campaign 'Q1 Outreach'",
  "data": {
    "integrity_score": 95.2,
    "needs_cleanup": false,
    "recommendations": ["Campaign tracking integrity is healthy"]
  }
}

# Nettoyage données (owners only)
POST /campaigns/123/cleanup-tracking/
Response: {
  "success": true,
  "message": "Cleanup completed for campaign 'Q1 Outreach'",
  "data": {
    "cleanup_successful": true,
    "actions_taken": ["Removed 2 deleted leads"],
    "before_integrity_score": 92.1,
    "after_integrity_score": 100.0
  }
}

ALL ENDPOINTS NOW RETURN STANDARDIZED RESPONSES WITH:
- success: boolean
- message: string (using CampaignSuccessMessages)
- data: object (structured data)
- meta: object (operation metadata)

ERROR RESPONSES USE STANDARDIZED ERROR MESSAGES:
- CampaignErrorMessages for campaign-specific errors
- CoreErrorMessages for general errors
- Proper HTTP status codes
- Consistent error format
"""