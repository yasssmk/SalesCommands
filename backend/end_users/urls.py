# apps/end_users/urls.py

from django.urls import path
from .views.user_view import (
    # ViewSets
    ClientAccountViewSet,
    UserRoleViewSet,
    OrganizationViewSet,
    TeamViewSet,
    UserViewSet,
    # Vues d'authentification
    UserLoginView,
    UserLogoutView,
    UserRefreshTokenView
)
from .views.sales_quota_views import SalesQuotaViewSet
from .views.sales_plan_views import SalesPlanViewSet  
from .views.sales_milestone_views import SalesMilestoneViewSet

app_name = 'end_users'

urlpatterns = [
    
    # =========================================================================
    # AUTHENTIFICATION - URLs existantes conservées pour compatibilité
    # =========================================================================
    
    path('login/', UserLoginView.as_view(), name='login'),
    path('logout/', UserLogoutView.as_view(), name='logout'),
    path('refresh-token/', UserRefreshTokenView.as_view(), name='refresh-token'),
    
    # =========================================================================
    # CLIENT ACCOUNTS MANAGEMENT - Niveau root du multi-tenant
    # =========================================================================
    
    # Client Accounts CRUD
    path('client-accounts/', ClientAccountViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='client-account-list'),
    
    path('client-accounts/<int:pk>/', ClientAccountViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='client-account-detail'),
    
    # Client Account Actions
    path('client-accounts/<int:pk>/stats/', ClientAccountViewSet.as_view({
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
    
    path('roles/<int:pk>/', UserRoleViewSet.as_view({
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
    
    path('users/<int:pk>/', UserViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='user-detail'),
    
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
    
    # =========================================================================
    # SALES PLANS MANAGEMENT - Gestion des plans commerciaux avec dashboard
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
    
    # Sales Plan Dashboard Actions
    path('sales-plans/<int:pk>/dashboard/', SalesPlanViewSet.as_view({
        'get': 'dashboard'
    }), name='sales-plan-dashboard'),
    
    path('sales-plans/<int:pk>/planning-analysis/', SalesPlanViewSet.as_view({
        'get': 'planning_analysis'
    }), name='sales-plan-planning-analysis'),
    
    path('sales-plans/<int:pk>/quick-summary/', SalesPlanViewSet.as_view({
        'get': 'quick_summary'
    }), name='sales-plan-quick-summary'),
    
    # Sales Plan Multi-User Actions
    path('sales-plans/my-plans/', SalesPlanViewSet.as_view({
        'get': 'my_plans'
    }), name='sales-plan-my-plans'),
    
    path('sales-plans/team-plans/', SalesPlanViewSet.as_view({
        'get': 'team_plans'
    }), name='sales-plan-team-plans'),
    
    # Sales Plan Management Actions
    path('sales-plans/<int:pk>/activate/', SalesPlanViewSet.as_view({
        'patch': 'activate'
    }), name='sales-plan-activate'),
    
    path('sales-plans/<int:pk>/pause/', SalesPlanViewSet.as_view({
        'patch': 'pause'
    }), name='sales-plan-pause'),
    
    path('sales-plans/<int:pk>/refresh-data/', SalesPlanViewSet.as_view({
        'post': 'refresh_data'
    }), name='sales-plan-refresh-data'),
    
    # =========================================================================
    # SALES MILESTONES MANAGEMENT - Gestion des jalons avec tracking automatique
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
    
    # Sales Milestone Tracking Actions
    path('sales-milestones/<int:pk>/update-progress/', SalesMilestoneViewSet.as_view({
        'post': 'update_progress'
    }), name='sales-milestone-update-progress'),
    
    path('sales-milestones/batch-update/', SalesMilestoneViewSet.as_view({
        'post': 'batch_update'
    }), name='sales-milestone-batch-update'),
    
    # Sales Milestone Filtering Actions
    path('sales-milestones/overdue/', SalesMilestoneViewSet.as_view({
        'get': 'overdue'
    }), name='sales-milestone-overdue'),
    
    path('sales-milestones/upcoming/', SalesMilestoneViewSet.as_view({
        'get': 'upcoming'
    }), name='sales-milestone-upcoming'),
    
    path('sales-milestones/by-plan/<int:plan_id>/', SalesMilestoneViewSet.as_view({
        'get': 'by_plan'
    }), name='sales-milestone-by-plan'),
    
    # Sales Milestone Management Actions
    path('sales-milestones/<int:pk>/mark-achieved/', SalesMilestoneViewSet.as_view({
        'patch': 'mark_achieved'
    }), name='sales-milestone-mark-achieved'),
    
    path('sales-milestones/<int:pk>/reset-progress/', SalesMilestoneViewSet.as_view({
        'patch': 'reset_progress'
    }), name='sales-milestone-reset-progress'),
    
    # =========================================================================
    # USER COLLECTIONS - Collections et filtres spécialisés
    # =========================================================================
    
    # Liste des managers avec métriques
    path('users/managers/', UserViewSet.as_view({
        'get': 'managers'
    }), name='user-managers'),
    
    # =========================================================================
    # ALIASES ET RACCOURCIS - Pour faciliter l'utilisation
    # =========================================================================
    
    # Raccourcis vers les éléments les plus utilisés
    path('my-performance/', UserViewSet.as_view({
        'get': 'performance'
    }), name='my-performance'),
    
    path('my-team-performance/', UserViewSet.as_view({
        'get': 'team_performance'
    }), name='my-team-performance'),
    
    # Raccourcis Sales Quotas
    path('my-quotas/', SalesQuotaViewSet.as_view({
        'get': 'my_quotas'
    }), name='my-quotas'),
    
    # Raccourcis Sales Plans  
    path('my-plans/', SalesPlanViewSet.as_view({
        'get': 'my_plans'
    }), name='my-plans'),
    
    # =========================================================================
    # DOCUMENTATION ET METADATA - URLs d'information
    # =========================================================================
    
    # Note: Ces endpoints pourraient être ajoutés plus tard pour l'API discovery
    # path('api-info/', APIInfoView.as_view(), name='api-info'),
    # path('endpoints/', EndpointsView.as_view(), name='endpoints'),
]