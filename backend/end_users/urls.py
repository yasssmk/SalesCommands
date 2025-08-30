# apps/end_users/urls.py

from django.urls import path
from .views.user_view import (
    # ViewSets
    ClientAccountViewSet,
    OrganizationViewSet,
    TeamViewSet,
    UserViewSet,
    # Vues d'authentification
    UserLoginView,
    UserLogoutView,
    UserRefreshTokenView,
    UserCurrentView
)
from .views.role_views import UserRoleViewSet 
from .views.sales_quota_views import SalesQuotaViewSet
from .views.sales_plan_views import SalesPlanViewSet  
from .views.sales_milestone_views import SalesMilestoneViewSet

app_name = 'client'

urlpatterns = [
    
    # =========================================================================
    # AUTHENTIFICATION - URLs existantes conservées pour compatibilité
    # =========================================================================
    
    path('login/', UserLoginView.as_view(), name='login'),
    path('logout/', UserLogoutView.as_view(), name='logout'),
    path('refresh-token/', UserRefreshTokenView.as_view(), name='refresh-token'),
    path('user/', UserCurrentView.as_view(), name='current-user'),
    
    # =========================================================================
    # CLIENT ACCOUNTS MANAGEMENT - Niveau root du multi-tenant
    # =========================================================================
    
    # Client Accounts CRUD
    path('client-accounts/', ClientAccountViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='client-account-list'),
    
    path('client-accounts/<uuid:pk>/', ClientAccountViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='client-account-detail'),
    
    # Client Account Actions
    path('client-accounts/<uuid:pk>/stats/', ClientAccountViewSet.as_view({
        'get': 'stats'
    }), name='client-account-stats'),
    
    # =========================================================================
    # USER ROLES MANAGEMENT - Gestion des rôles et permissions
    # =========================================================================
    
    # User Roles CRUD
    path('roles/', UserRoleViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='user-role-list'),
    
    # CORRECTION CRITIQUE : UUID pk au lieu de int pk
    path('roles/<uuid:pk>/', UserRoleViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='user-role-detail'),
    
    # User Role Actions
    path('roles/permissions-matrix/', UserRoleViewSet.as_view({
        'get': 'permissions_matrix'
    }), name='user-role-permissions-matrix'),
    
    # =========================================================================
    # ORGANIZATIONS MANAGEMENT - Gestion des organisations
    # =========================================================================
    
    # Organizations CRUD
    path('organizations/', OrganizationViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='organization-list'),
    
    path('organizations/<int:pk>/', OrganizationViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='organization-detail'),
    
    # Organization Actions
    path('organizations/<int:pk>/hierarchy/', OrganizationViewSet.as_view({
        'get': 'hierarchy'
    }), name='organization-hierarchy'),
    
    # =========================================================================
    # TEAMS MANAGEMENT - Gestion des équipes
    # =========================================================================
    
    # Teams CRUD
    path('teams/', TeamViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='team-list'),
    
    path('teams/<int:pk>/', TeamViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='team-detail'),
    
    # Team Actions
    path('teams/<int:pk>/members-performance-summary/', TeamViewSet.as_view({
        'get': 'members_performance_summary'
    }), name='team-members-performance-summary'),
    
    # =========================================================================
    # USERS MANAGEMENT - Gestion des utilisateurs et performances
    # =========================================================================
    
    # Users CRUD
    path('users/', UserViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='user-list'),
    
    path('users/<uuid:pk>/', UserViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='user-detail'),

    path('users/superusers/', UserViewSet.as_view({
        'get': 'superusers'
    }), name='user-superusers'),
    
    # Accorder/Retirer le statut superuser
    path('users/grant-superuser/', UserViewSet.as_view({
        'post': 'grant_superuser'
    }), name='user-grant-superuser'),

    path('users/<uuid:pk>/change-password/', UserViewSet.as_view({
        'patch': 'change_password'
    }), name='user-change-password'),

    # Création en lot
    path('users/bulk-create/', UserViewSet.as_view({
        'post': 'bulk_create'
    }), name='user-bulk-create'),

    # Mise à jour en lot
    path('users/bulk-update/', UserViewSet.as_view({
        'patch': 'bulk_update'
    }), name='user-bulk-update'),

    # Suppression en lot
    path('users/bulk-delete/', UserViewSet.as_view({
        'delete': 'bulk_delete'
    }), name='user-bulk-delete'),
    
    # =========================================================================
    # USER PERFORMANCE INTEGRATION - Intégration UserPerformanceService
    # =========================================================================
    
    # Performance individuelle
    path('users/<int:pk>/performance/', UserViewSet.as_view({
        'get': 'performance'
    }), name='user-performance'),
    
    # Performance équipe de l'utilisateur connecté
    path('users/team-performance/', UserViewSet.as_view({
        'get': 'team_performance'
    }), name='user-team-performance'),
    
    # Performance des utilisateurs managés (pour managers)
    path('users/<int:pk>/managed-users-performance/', UserViewSet.as_view({
        'get': 'managed_users_performance'
    }), name='user-managed-users-performance'),
    
    # =========================================================================
    # SALES QUOTAS MANAGEMENT - Gestion des quotas de vente (MVP)
    # =========================================================================
    
    # Sales Quotas CRUD
    path('sales-quotas/', SalesQuotaViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='sales-quota-list'),
    
    path('sales-quotas/<int:pk>/', SalesQuotaViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='sales-quota-detail'),
    
    # Sales Quota Actions
    path('sales-quotas/<int:pk>/performance/', SalesQuotaViewSet.as_view({
        'get': 'performance'
    }), name='sales-quota-performance'),
    
    path('sales-quotas/team-summary/', SalesQuotaViewSet.as_view({
        'get': 'team_summary'
    }), name='sales-quota-team-summary'),
    
    path('sales-quotas/my-quotas/', SalesQuotaViewSet.as_view({
        'get': 'my_quotas'
    }), name='sales-quota-my-quotas'),
    
    # Sales Quota Status Management
    path('sales-quotas/<int:pk>/activate/', SalesQuotaViewSet.as_view({
        'patch': 'activate'
    }), name='sales-quota-activate'),
    
    path('sales-quotas/<int:pk>/deactivate/', SalesQuotaViewSet.as_view({
        'patch': 'deactivate'
    }), name='sales-quota-deactivate'),
    
    path('sales-quotas/<int:pk>/duplicate/', SalesQuotaViewSet.as_view({
        'post': 'duplicate'
    }), name='sales-quota-duplicate'),
    
    path('sales-quotas/team-performance/', SalesQuotaViewSet.as_view({
        'get': 'team_performance'
    }), name='sales-quota-team-performance'),
    
    # =========================================================================
    # ✅ SALES PLANS MANAGEMENT - Gestion simplifiée MVP (3 actions)
    # =========================================================================
    
    # Sales Plans CRUD
    path('sales-plans/', SalesPlanViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='sales-plan-list'),
    
    path('sales-plans/<int:pk>/', SalesPlanViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='sales-plan-detail'),
    
    # ✅ ACTIONS SIMPLIFIÉES (3 seulement)
    
    # Dashboard complet (remplace planning_analysis supprimé)
    path('sales-plans/<int:pk>/dashboard/', SalesPlanViewSet.as_view({
        'get': 'dashboard'
    }), name='sales-plan-dashboard'),
    
    # Plans utilisateur courant
    path('sales-plans/my-plans/', SalesPlanViewSet.as_view({
        'get': 'my_plans'
    }), name='sales-plan-my-plans'),
    
    # Gestion statuts (remplace pause/refresh-data supprimés)
    path('sales-plans/<int:pk>/activate/', SalesPlanViewSet.as_view({
        'patch': 'activate'
    }), name='sales-plan-activate'),
    
    # ❌ SUPPRIMÉ (actions trop complexes pour MVP) :
    # - planning_analysis → Doublonne avec dashboard
    # - quick_summary → Intégré dans retrieve/dashboard  
    # - team_plans → Complexité manager non essentielle
    # - pause → activate() gère tous les statuts
    # - refresh_data → Signaux automatiques suffisent
    
    # =========================================================================
    # ✅ SALES MILESTONES MANAGEMENT - Gestion simplifiée MVP (2 actions)
    # =========================================================================
    
    # Sales Milestones CRUD
    path('sales-milestones/', SalesMilestoneViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='sales-milestone-list'),
    
    path('sales-milestones/<int:pk>/', SalesMilestoneViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='sales-milestone-detail'),
    
    # ✅ ACTIONS SIMPLIFIÉES (2 seulement)
    
    # Force recalcul milestone individuel
    path('sales-milestones/<int:pk>/update-progress/', SalesMilestoneViewSet.as_view({
        'post': 'update_progress'
    }), name='sales-milestone-update-progress'),
    
    # Milestones utilisateur courant
    path('sales-milestones/my-milestones/', SalesMilestoneViewSet.as_view({
        'get': 'my_milestones'
    }), name='sales-milestone-my-milestones'),
    
    # ❌ SUPPRIMÉ → REMPLACÉ par query params dans list() :
    # - overdue → GET /sales-milestones/?period=overdue
    # - upcoming → GET /sales-milestones/?period=upcoming&days=30
    # - by_plan → GET /sales-milestones/?sales_plan_id=123
    # 
    # ❌ SUPPRIMÉ → Logique intégrée dans update() standard :
    # - batch_update → Boucle API standard côté frontend
    # - mark_achieved → PATCH /sales-milestones/{id}/ avec status
    # - reset_progress → PATCH /sales-milestones/{id}/ avec valeurs reset
    
    # =========================================================================
    # USER COLLECTIONS - Collections et filtres spécialisés (INCHANGÉ)
    # =========================================================================
    
    # Liste des managers avec métriques
    path('users/managers/', UserViewSet.as_view({
        'get': 'managers'
    }), name='user-managers'),
    
    # =========================================================================
    # ✅ ALIASES ET RACCOURCIS - Cohérents avec simplifications
    # =========================================================================
    
    # Raccourcis vers les éléments les plus utilisés
    path('my-performance/', UserViewSet.as_view({
        'get': 'performance'
    }), name='my-performance'),
    
    path('my-team-performance/', UserViewSet.as_view({
        'get': 'team_performance'
    }), name='my-team-performance'),
    
    # Raccourcis Sales Quotas (INCHANGÉ)
    path('my-quotas/', SalesQuotaViewSet.as_view({
        'get': 'my_quotas'
    }), name='my-quotas'),
    
    # ✅ Raccourcis Sales Plans (cohérents avec simplifications)
    path('my-plans/', SalesPlanViewSet.as_view({
        'get': 'my_plans'
    }), name='my-plans'),
    
    # ✅ NOUVEAU : Raccourci Sales Milestones
    path('my-milestones/', SalesMilestoneViewSet.as_view({
        'get': 'my_milestones'
    }), name='my-milestones'),
    
    # =========================================================================
    # DOCUMENTATION ET METADATA - URLs d'information (INCHANGÉ)
    # =========================================================================
    
    # Note: Ces endpoints pourraient être ajoutés plus tard pour l'API discovery
    # path('api-info/', APIInfoView.as_view(), name='api-info'),
    # path('endpoints/', EndpointsView.as_view(), name='endpoints'),
    
    # =========================================================================
    # ✅ COMPATIBILITÉ BACKWARD - Redirections temporaires
    # =========================================================================
    
    # Note: Si certaines URLs supprimées sont utilisées par le frontend,
    # on peut temporairement ajouter des redirections ou des vues de fallback
    # qui retournent des erreurs explicites avec les nouvelles URLs à utiliser.
    
    # Exemple pour migration progressive :
    # path('sales-plans/<int:pk>/planning-analysis/', 
    #      RedirectView.as_view(pattern_name='sales-plan-dashboard'), 
    #      name='sales-plan-planning-analysis-deprecated'),
]

# =========================================================================
# ✅ RÉSUMÉ DES MODIFICATIONS URL
# =========================================================================

"""
SALES PLANS - Actions réduites (7 → 3) :
✅ GARDÉ :
- dashboard() : Analyse complète
- my_plans() : Plans utilisateur  
- activate() : Gestion statuts

❌ SUPPRIMÉ :
- planning_analysis → dashboard() plus complet
- quick_summary → Intégré dans retrieve()
- team_plans → Complexité non MVP
- pause → activate() gère tous statuts  
- refresh_data → Signaux automatiques

SALES MILESTONES - Actions réduites (7 → 2) :
✅ GARDÉ :
- update_progress() : Force recalcul
- my_milestones() : Milestones utilisateur (NOUVEAU)

❌ SUPPRIMÉ → Query params :
- overdue → ?period=overdue
- upcoming → ?period=upcoming&days=X
- by_plan → ?sales_plan_id=X

❌ SUPPRIMÉ → Update standard :
- batch_update → Boucle API frontend
- mark_achieved → PATCH standard
- reset_progress → PATCH standard

BÉNÉFICES :
✅ URLs cohérentes avec ViewSets simplifiés
✅ API plus prévisible et maintenable
✅ Logique de filtrage via query params standard
✅ Moins de complexité pour frontend
✅ Architecture MVP cohérente
"""