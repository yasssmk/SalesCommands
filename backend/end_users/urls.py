# from django.urls import path
# from .views import AdminCreateUserView, UserLoginView, UserLogoutView, UserRefreshTokenView

# urlpatterns = [
#     path('admin-create/', AdminCreateUserView.as_view(), name='admin_create_user'),
#     path('login/', UserLoginView.as_view(), name='login'),
#     path('logout/', UserLogoutView.as_view(), name='logout'),

# ]

# end_users/urls.py

# end_users/urls.py

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
    
    # =========================================================================
    # DOCUMENTATION ET METADATA - URLs d'information
    # =========================================================================
    
    # Note: Ces endpoints pourraient être ajoutés plus tard pour l'API discovery
    # path('api-info/', APIInfoView.as_view(), name='api-info'),
    # path('endpoints/', EndpointsView.as_view(), name='endpoints'),
]

# =========================================================================
# URL PATTERNS DOCUMENTATION
# =========================================================================

"""
ORGANISATION DES URLs end_users:

📁 AUTHENTIFICATION
├── /login/                          → Connexion utilisateur
├── /logout/                         → Déconnexion utilisateur  
└── /refresh-token/                  → Rafraîchir les tokens

📁 CLIENT ACCOUNTS (Multi-tenant root)
├── /client-accounts/                → Liste/Création comptes clients
├── /client-accounts/{id}/           → Détail/Modification compte client
└── /client-accounts/{id}/stats/     → Statistiques détaillées client

📁 USER ROLES (Permissions)
├── /roles/                          → Liste/Création rôles
├── /roles/{id}/                     → Détail/Modification rôle
└── /roles/permissions-matrix/       → Matrice permissions tous rôles

📁 ORGANIZATIONS (Hiérarchie)
├── /organizations/                  → Liste/Création organisations
├── /organizations/{id}/             → Détail/Modification organisation
└── /organizations/{id}/hierarchy/   → Hiérarchie complète (orgs/équipes/membres)

📁 TEAMS (Équipes)
├── /teams/                          → Liste/Création équipes
├── /teams/{id}/                     → Détail/Modification équipe
└── /teams/{id}/members-performance-summary/ → Résumé performances membres

📁 USERS (Utilisateurs)
├── /users/                          → Liste/Création utilisateurs
├── /users/{id}/                     → Détail/Modification utilisateur
└── /users/managers/                 → Liste managers avec métriques

📁 SALES QUOTAS (Quotas de vente - MVP)
├── /sales-quotas/                   → Liste/Création quotas
├── /sales-quotas/{id}/              → Détail/Modification quota
├── /sales-quotas/{id}/performance/  → Performance détaillée quota
├── /sales-quotas/team-summary/      → Résumé quotas équipe
├── /sales-quotas/my-quotas/         → Mes quotas personnels
├── /sales-quotas/{id}/activate/     → Activer quota
└── /sales-quotas/{id}/deactivate/   → Désactiver quota

📁 PERFORMANCE INTEGRATION (Sales Plan Foundation)
├── /users/{id}/performance/         → Métriques individuelles (période configurable)
├── /users/team-performance/         → Performances équipe utilisateur connecté
├── /users/{id}/managed-users-performance/ → Performances utilisateurs managés
├── /my-performance/                 → Raccourci performances personnelles
├── /my-team-performance/           → Raccourci performances équipe
└── /my-quotas/                     → Raccourci mes quotas

PARAMÈTRES QUERYSTRING SUPPORTÉS:

🔍 FILTRES COMMUNS (tous les endpoints list):
- ?active_only=true/false           → Filtrer éléments actifs uniquement  
- ?managers_only=true/false         → Filtrer managers uniquement
- ?search=terme                     → Recherche textuelle
- ?ordering=field,-field            → Tri (- pour desc)

📊 PARAMÈTRES PERFORMANCE:
- ?period_start=YYYY-MM-DD          → Début période analyse
- ?period_end=YYYY-MM-DD            → Fin période analyse
- (défaut: mois actuel si non spécifié)

🎯 PARAMÈTRES SALES QUOTAS:
- ?target_type=CLOSED_WON,PIPELINE  → Filtrer par type d'objectif
- ?current_period=true              → Quotas de la période courante
- ?user={id}                        → Quotas d'un utilisateur spécifique
- ?user__team={id}                  → Quotas d'une équipe

EXEMPLES D'UTILISATION:

📈 RÉCUPÉRER PERFORMANCES UTILISATEUR:
GET /client/users/123/performance/?period_start=2024-01-01&period_end=2024-01-31

📊 VUE MANAGER - PERFORMANCES ÉQUIPE:
GET /client/users/456/managed-users-performance/?period_start=2024-01-01&period_end=2024-01-31

🎯 MES QUOTAS ACTIFS:
GET /client/my-quotas/?active_only=true

🎯 PERFORMANCE D'UN QUOTA:
GET /client/sales-quotas/789/performance/

🎯 RÉSUMÉ QUOTAS ÉQUIPE:
GET /client/sales-quotas/team-summary/

🎯 QUOTAS PÉRIODE COURANTE:
GET /client/sales-quotas/?current_period=true&active_only=true

🏢 HIÉRARCHIE ORGANISATION COMPLÈTE:
GET /client/organizations/789/hierarchy/

👥 LISTE MANAGERS AVEC MÉTRIQUES:
GET /client/users/managers/?active_only=true

📋 STATISTIQUES CLIENT:
GET /client/client-accounts/101/stats/

🔐 MATRICE PERMISSIONS:
GET /client/roles/permissions-matrix/

INTÉGRATION SALES PLAN ACTUELLE:

✅ MVP SALES QUOTAS IMPLÉMENTÉ:
- Gestion complète des quotas de vente individuels
- Performance temps réel avec intégration CRM 
- Support équipes et organisations
- Calculs optimisés et projections

🚀 ÉVOLUTION FUTURE PHASE 2:
1. /users/{id}/performance/ → Base pour dashboard Sales Plan individuel
2. /users/team-performance/ → Base pour dashboard Sales Plan équipe  
3. /users/{id}/managed-users-performance/ → Base pour vue manager Sales Plan
4. Les quotas serviront de fondation pour SalesPlans avec jalons (milestones)

Cette architecture permet une évolution naturelle vers les fonctionnalités Sales Plan avancées.
"""