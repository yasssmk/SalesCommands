# apps/campaign/urls.py (version complète mise à jour)
from django.urls import path
from .views.campaign_management_views import CampaignManagementViewSet, ActivityResultViewSet
from .views.campaign_views import CampaignViewSet
from .views.campaign_target_views import CampaignTargetViewSet
from .views.campaign_objective_views import CampaignObjectiveViewSet
from .views.campaign_stakeholder_views import CampaignStakeholderViewSet

urlpatterns = [
    
    # =========================================================================
    # CAMPAIGN MANAGEMENT - PRINCIPAL (Source unique pour dashboard + gestion)
    # =========================================================================
    
    # Basic CRUD
    path('', CampaignManagementViewSet.as_view({'get': 'list', 'post': 'create'}), name='campaign-list'),
    path('<int:pk>/', CampaignManagementViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='campaign-detail'),
    
    # Campaign Creation with Targets
    path('create-with-targets/', CampaignManagementViewSet.as_view({'post': 'create_with_targets'}), name='campaign-create-with-targets'),
    
    # Campaign Control Actions
    path('<int:pk>/start/', CampaignManagementViewSet.as_view({'post': 'start_campaign'}), name='campaign-start'),
    path('<int:pk>/pause/', CampaignManagementViewSet.as_view({'post': 'pause_campaign'}), name='campaign-pause'),
    path('<int:pk>/resume/', CampaignManagementViewSet.as_view({'post': 'resume_campaign'}), name='campaign-resume'),
    
    # Campaign Playlist & Summary
    path('<int:pk>/playlist/', CampaignManagementViewSet.as_view({'get': 'playlist'}), name='campaign-playlist'),
    path('<int:pk>/summary/', CampaignManagementViewSet.as_view({'get': 'summary'}), name='campaign-summary'),
    path('<int:pk>/contacts-responses/', CampaignManagementViewSet.as_view({'get': 'contacts_with_responses'}), name='campaign-contacts-responses'),
    
    # =========================================================================
    # CAMPAIGN ANALYTICS & DASHBOARD (SOURCE UNIQUE - NOUVEAUX ENDPOINTS)
    # =========================================================================
    
    # Dashboard complet (service analytics)
    path('<int:pk>/dashboard/', CampaignManagementViewSet.as_view({'get': 'dashboard'}), name='campaign-dashboard'),
    
    # Dashboard rapide (helpers modèle)
    path('<int:pk>/dashboard-summary/', CampaignManagementViewSet.as_view({'get': 'dashboard_summary'}), name='campaign-dashboard-summary'),
    
    # Analytics spécialisés
    path('<int:pk>/objectives-progress/', CampaignManagementViewSet.as_view({'get': 'objectives_progress'}), name='campaign-objectives-progress'),
    path('<int:pk>/conversion-analysis/', CampaignManagementViewSet.as_view({'get': 'conversion_analysis'}), name='campaign-conversion-analysis'),
    
    # Métriques simples et maintenance
    path('<int:pk>/metrics/', CampaignManagementViewSet.as_view({'get': 'metrics'}), name='campaign-metrics'),
    path('<int:pk>/integrity-check/', CampaignManagementViewSet.as_view({'post': 'integrity_check'}), name='campaign-integrity-check'),
    path('<int:pk>/cleanup-tracking/', CampaignManagementViewSet.as_view({'post': 'cleanup_tracking'}), name='campaign-cleanup-tracking'),
    
    # =========================================================================
    # ACCOUNT/CONTACT MANAGEMENT
    # =========================================================================
    
    path('account-campaigns/', CampaignManagementViewSet.as_view({'get': 'account_campaigns'}), name='account-campaigns'),
    path('<int:pk>/remove-account/', CampaignManagementViewSet.as_view({'post': 'remove_account'}), name='campaign-remove-account'),
    path('<int:pk>/remove-contact/', CampaignManagementViewSet.as_view({'post': 'remove_contact'}), name='campaign-remove-contact'),
    
    # =========================================================================
    # ACTIVITY MANAGEMENT
    # =========================================================================
    
    path('<int:pk>/activities/', CampaignManagementViewSet.as_view({'get': 'activities'}), name='campaign-activities'),
    path('<int:pk>/account-activities/', CampaignManagementViewSet.as_view({'get': 'account_activities'}), name='campaign-account-activities'),
    path('<int:pk>/contact-activities/', CampaignManagementViewSet.as_view({'get': 'contact_activities'}), name='campaign-contact-activities'),
    path('<int:pk>/add-manual-activity/', CampaignManagementViewSet.as_view({'post': 'add_manual_activity'}), name='campaign-add-manual-activity'),
    
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
ARCHITECTURE CLARIFIÉE - SOURCE UNIQUE POUR DASHBOARD :

📊 DASHBOARD & ANALYTICS (CampaignManagementViewSet - SOURCE UNIQUE) :
GET    /campaigns/{id}/dashboard/                     - 🎯 Dashboard complet (service analytics)
GET    /campaigns/{id}/dashboard-summary/             - 🎯 Dashboard rapide (helpers modèle)  
GET    /campaigns/{id}/objectives-progress/           - 🎯 Focus objectifs avec détails
GET    /campaigns/{id}/conversion-analysis/           - 🎯 Focus taux de conversion
GET    /campaigns/{id}/metrics/                       - 🎯 Métriques brutes tracking
POST   /campaigns/{id}/integrity-check/               - 🔧 Vérification intégrité données
POST   /campaigns/{id}/cleanup-tracking/              - 🔧 Nettoyage données invalides

🏗️ CAMPAIGN MANAGEMENT (CampaignManagementViewSet - GESTION PRINCIPALE) :
POST   /campaigns/create-with-targets/                - Création campagne + targets + activités
POST   /campaigns/{id}/start/                         - Démarrer campagne
GET    /campaigns/{id}/playlist/                      - Playlist activités à faire
GET    /campaigns/{id}/summary/                       - Résumé progression activités
POST   /campaigns/{id}/pause/                         - Pause campagne
POST   /campaigns/{id}/resume/                        - Reprendre campagne

📋 OBJECTIVES CRUD UNIQUEMENT (CampaignObjectiveViewSet - PAS D'ANALYTICS) :
GET    /campaigns/objectives/                         - Liste objectifs
POST   /campaigns/objectives/                         - Créer objectif
GET    /campaigns/objectives/{id}/                    - Détail objectif
PUT    /campaigns/objectives/{id}/                    - Modifier objectif
DELETE /campaigns/objectives/{id}/                    - Supprimer objectif
POST   /campaigns/objectives/{id}/set-as-primary/     - Définir comme primaire
POST   /campaigns/objectives/{id}/sync-progress/      - Resynchroniser progression

🎯 TARGETS CRUD (CampaignTargetViewSet) :
GET    /campaigns/targets/                            - Liste targets
POST   /campaigns/targets/                            - Créer target
POST   /campaigns/targets/bulk-create/                - Créer plusieurs targets

👥 STAKEHOLDERS CRUD (CampaignStakeholderViewSet) :
GET    /campaigns/stakeholders/                       - Liste stakeholders
POST   /campaigns/stakeholders/                       - Créer stakeholder
POST   /campaigns/stakeholders/bulk-add/              - Ajouter plusieurs stakeholders

✅ ACTIVITY RESULTS (ActivityResultViewSet) :
POST   /campaigns/activities/{id}/complete/           - Compléter activité avec résultat
POST   /campaigns/activities/{id}/add-response/       - Ajouter réponse email/LinkedIn
GET    /campaigns/activities/next-step-options/       - Options next steps disponibles
POST   /campaigns/activities/next-step-process/       - Traiter choix next step

PRINCIPE ARCHITECTURAL :
- 🎯 Dashboard/Analytics → CampaignManagementViewSet (SOURCE UNIQUE)
- 📋 CRUD Objectifs → CampaignObjectiveViewSet (CRUD UNIQUEMENT)  
- 🏗️ Gestion Campagne → CampaignManagementViewSet (PRINCIPAL)
- ✅ Résultats → ActivityResultViewSet (SPÉCIALISÉ)

EXEMPLES D'UTILISATION FRONTEND :
- Afficher dashboard → GET /campaigns/123/dashboard/
- Modifier objectif → PUT /campaigns/objectives/456/
- Voir progression objectifs → GET /campaigns/123/objectives-progress/
- Démarrer campagne → POST /campaigns/123/start/
"""