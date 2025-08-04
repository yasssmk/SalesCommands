# from django.urls import path
# from .views import AdminCreateUserView, UserLoginView, UserLogoutView, UserRefreshTokenView

# urlpatterns = [
#     path('admin-create/', AdminCreateUserView.as_view(), name='admin_create_user'),
#     path('login/', UserLoginView.as_view(), name='login'),
#     path('logout/', UserLogoutView.as_view(), name='logout'),

# ]

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

📁 PERFORMANCE INTEGRATION (Sales Plan Foundation)
├── /users/{id}/performance/         → Métriques individuelles (période configurable)
├── /users/team-performance/         → Performances équipe utilisateur connecté
├── /users/{id}/managed-users-performance/ → Performances utilisateurs managés
├── /my-performance/                 → Raccourci performances personnelles
└── /my-team-performance/           → Raccourci performances équipe

PARAMÈTRES QUERYSTRING SUPPORTÉS:

🔍 FILTRES COMMUNS (tous les endpoints list):
- ?active_only=true/false           → Filtrer utilisateurs actifs uniquement  
- ?managers_only=true/false         → Filtrer managers uniquement
- ?search=terme                     → Recherche textuelle
- ?ordering=field,-field            → Tri (- pour desc)

📊 PARAMÈTRES PERFORMANCE:
- ?period_start=YYYY-MM-DD          → Début période analyse
- ?period_end=YYYY-MM-DD            → Fin période analyse
- (défaut: mois actuel si non spécifié)

EXEMPLES D'UTILISATION:

📈 RÉCUPÉRER PERFORMANCES UTILISATEUR:
GET /client/users/123/performance/?period_start=2024-01-01&period_end=2024-01-31

📊 VUE MANAGER - PERFORMANCES ÉQUIPE:
GET /client/users/456/managed-users-performance/?period_start=2024-01-01&period_end=2024-01-31

🏢 HIÉRARCHIE ORGANISATION COMPLÈTE:
GET /client/organizations/789/hierarchy/

👥 LISTE MANAGERS AVEC MÉTRIQUES:
GET /client/users/managers/?active_only=true

📋 STATISTIQUES CLIENT:
GET /client/client-accounts/101/stats/

🔐 MATRICE PERMISSIONS:
GET /client/roles/permissions-matrix/

INTÉGRATION FUTURE SALES PLAN:

Les endpoints de performance sont conçus pour s'intégrer parfaitement avec le futur système Sales Plan:

1. /users/{id}/performance/ → Base pour dashboard Sales Plan individuel
2. /users/team-performance/ → Base pour dashboard Sales Plan équipe  
3. /users/{id}/managed-users-performance/ → Base pour vue manager Sales Plan
4. Les métriques retournées (leads, opportunities, campaigns, meetings) sont les fondations des calculs de quotas

Cette architecture permet une transition fluide vers les fonctionnalités Sales Plan avancées en Phase 2.
"""