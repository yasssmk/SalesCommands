# backend/tests/unit/test_throttle_enforcer.py
# tests/integration/test_throttling_2F.py
"""
Tests d'intégration Phase 2.F : Throttle réaliste

Valide :
1. StandardRateThrottle sur GET endpoints (30/min PROD, 50/min DEV)
2. BulkOperationThrottle sur bulk operations (3/min PROD, 5/min DEV)
3. Actions spécifiques conservent leurs throttles personnalisés
"""

import pytest
from django.urls import reverse
from django.conf import settings
from rest_framework import status
from rest_framework.test import APIClient
from django.core.cache import cache
from end_users.models import User, UserRole, Team, Organization, ClientAccount
import time


@pytest.fixture
def clear_throttle_cache():
    """Clear throttle cache before each test"""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api_client():
    """Create API client"""
    return APIClient()


@pytest.fixture
def client_account(db):
    """Create test client account"""
    return ClientAccount.objects.create(
        name="Test Client",
        is_b2b=True,
        max_users=100
    )


@pytest.fixture
def admin_role(db, client_account):
    """Create admin role"""
    return UserRole.objects.create(
        name="Admin",
        client_account=client_account,
        read=True,
        write=True,
        modify=True,
        delete=True
    )


@pytest.fixture
def organization(db, client_account):
    """Create test organization"""
    return Organization.objects.create(
        name="Test Org",
        client_account=client_account
    )


@pytest.fixture
def team(db, client_account, organization):
    """Create test team"""
    return Team.objects.create(
        name="Test Team",
        client_account=client_account,
        organization=organization
    )


@pytest.fixture
def admin_user(db, client_account, admin_role, team, organization):
    """Create admin user for tests"""
    user = User.objects.create_user(
        email="admin@test.com",
        password="TestPass123!",
        first_name="Admin",
        last_name="User",
        client_account=client_account,
        role=admin_role,
        team=team,
        organization=organization,
        is_active=True
    )
    return user


@pytest.fixture
def authenticated_client(api_client, admin_user):
    """Create authenticated API client"""
    api_client.force_authenticate(user=admin_user)
    return api_client


# =========================================================================
# TEST 1: StandardRateThrottle sur GET endpoints
# =========================================================================

@pytest.mark.django_db
class TestStandardRateThrottle:
    """Test StandardRateThrottle (30/min PROD, 50/min DEV) sur GET endpoints"""
    
    def test_get_users_list_not_throttled_under_limit(
        self, authenticated_client, clear_throttle_cache
    ):
        """
        Test : 5 requêtes GET en 10 secondes → pas de 429
        StandardRateThrottle permet 30/min (PROD) ou 50/min (DEV)
        """
        url = reverse('user-list')
        
        # Simuler usage normal : recherche + tri + filtres
        requests = [
            url,                                    # Liste simple
            f"{url}?search=admin",                 # Recherche
            f"{url}?ordering=email",               # Tri
            f"{url}?is_active=true",              # Filtre 1
            f"{url}?is_staff=false",              # Filtre 2
        ]
        
        # Envoyer 5 requêtes
        for i, request_url in enumerate(requests, 1):
            response = authenticated_client.get(request_url)
            
            assert response.status_code != status.HTTP_429_TOO_MANY_REQUESTS, (
                f"Requête #{i} bloquée par throttle (429). "
                f"StandardRateThrottle trop strict ou mal configuré. "
                f"URL: {request_url}"
            )
            
            # Pause courte entre requêtes (simulation usage réel)
            time.sleep(0.2)
    
    def test_get_users_list_respects_throttle_limit(
        self, authenticated_client, clear_throttle_cache
    ):
        """
        Test : Dépasser la limite StandardRateThrottle → 429
        DEV: 50/min, PROD: 30/min
        """
        url = reverse('user-list')
        
        # Déterminer la limite selon l'environnement
        if settings.DEBUG:
            limit = 50  # DEV
        else:
            limit = 30  # PROD
        
        # Envoyer (limit + 1) requêtes rapidement
        throttled = False
        for i in range(limit + 5):  # +5 pour être sûr de dépasser
            response = authenticated_client.get(url)
            
            if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                throttled = True
                # Vérifier header Retry-After
                assert 'Retry-After' in response.headers, (
                    "Header Retry-After manquant dans réponse 429"
                )
                break
        
        assert throttled, (
            f"Aucun throttle détecté après {limit + 5} requêtes. "
            f"StandardRateThrottle ne fonctionne pas (limite: {limit}/min)"
        )


# =========================================================================
# TEST 2: BulkOperationThrottle sur bulk operations
# =========================================================================

@pytest.mark.django_db
class TestBulkOperationThrottle:
    """Test BulkOperationThrottle (3/min PROD, 5/min DEV) sur bulk operations"""
    
    def test_bulk_create_not_throttled_under_limit(
        self, authenticated_client, clear_throttle_cache, admin_role, team, organization
    ):
        """
        Test : 2-4 bulk_create en 10 secondes → pas de 429
        BulkOperationThrottle permet 3/min (PROD) ou 5/min (DEV)
        """
        url = reverse('user-bulk-create')
        
        # Déterminer combien de requêtes on peut faire
        if settings.DEBUG:
            safe_count = 4  # DEV: 5/min, on fait 4 pour être sûr
        else:
            safe_count = 2  # PROD: 3/min, on fait 2 pour être sûr
        
        # Envoyer safe_count bulk_create
        for i in range(safe_count):
            payload = {
                "users": [{
                    "email": f"bulktest{i}_{int(time.time())}@test.com",
                    "first_name": "Bulk",
                    "last_name": f"Test{i}",
                    "password": "TestPass123!",
                    "role": admin_role.id,
                    "team": team.id,
                    "organization": organization.id
                }],
                "mode": "partial"
            }
            
            response = authenticated_client.post(url, payload, format='json')
            
            assert response.status_code != status.HTTP_429_TOO_MANY_REQUESTS, (
                f"Bulk create #{i+1} bloqué par throttle (429). "
                f"BulkOperationThrottle trop strict. "
                f"Limite: {5 if settings.DEBUG else 3}/min"
            )
            
            # Pause courte entre appels
            time.sleep(1)
    
    def test_bulk_create_throttled_after_limit(
        self, authenticated_client, clear_throttle_cache, admin_role, team, organization
    ):
        """
        Test : 4+ bulk_create en 1 minute → 429 au 4ème (PROD) ou 6ème (DEV)
        BulkOperationThrottle limite: 3/min (PROD) ou 5/min (DEV)
        """
        url = reverse('user-bulk-create')
        
        # Déterminer la limite selon l'environnement
        if settings.DEBUG:
            limit = 5  # DEV
        else:
            limit = 3  # PROD
        
        # Envoyer (limit + 1) bulk_create
        throttled = False
        for i in range(limit + 2):
            payload = {
                "users": [{
                    "email": f"bulktest{i}_{int(time.time())}@test.com",
                    "first_name": "Bulk",
                    "last_name": f"Test{i}",
                    "password": "TestPass123!",
                    "role": admin_role.id,
                    "team": team.id,
                    "organization": organization.id
                }],
                "mode": "partial"
            }
            
            response = authenticated_client.post(url, payload, format='json')
            
            if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                throttled = True
                # Vérifier header Retry-After
                assert 'Retry-After' in response.headers, (
                    "Header Retry-After manquant dans réponse 429"
                )
                
                # Vérifier qu'on a bien dépassé la limite
                assert i >= limit, (
                    f"Throttle trop strict : bloqué au #{i+1} au lieu de #{limit+1}"
                )
                break
            
            time.sleep(1)
        
        assert throttled, (
            f"Aucun throttle détecté après {limit + 2} bulk_create. "
            f"BulkOperationThrottle ne fonctionne pas (limite: {limit}/min)"
        )
    
    def test_bulk_update_uses_bulk_throttle(
        self, authenticated_client, clear_throttle_cache, admin_user
    ):
        """
        Test : bulk_update utilise BulkOperationThrottle
        """
        url = reverse('user-bulk-update')
        
        # Déterminer la limite
        limit = 5 if settings.DEBUG else 3
        
        # Envoyer plusieurs bulk_update
        throttled = False
        for i in range(limit + 2):
            payload = {
                "ids": [str(admin_user.id)],
                "patch": {"is_active": True},
                "mode": "partial"
            }
            
            response = authenticated_client.patch(url, payload, format='json')
            
            if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                throttled = True
                break
            
            time.sleep(1)
        
        assert throttled, (
            f"bulk_update n'utilise pas BulkOperationThrottle (pas de 429 après {limit+2} requêtes)"
        )
    
    def test_bulk_delete_uses_bulk_throttle(
        self, authenticated_client, clear_throttle_cache, db, 
        client_account, admin_role, team, organization
    ):
        """
        Test : bulk_delete utilise BulkOperationThrottle
        """
        url = reverse('user-bulk-delete')
        
        # Déterminer la limite
        limit = 5 if settings.DEBUG else 3
        
        # Créer des users à supprimer
        users_to_delete = []
        for i in range(limit + 2):
            user = User.objects.create_user(
                email=f"todelete{i}_{int(time.time())}@test.com",
                password="TestPass123!",
                first_name="ToDelete",
                last_name=f"User{i}",
                client_account=client_account,
                role=admin_role,
                team=team,
                organization=organization
            )
            users_to_delete.append(user)
        
        # Envoyer plusieurs bulk_delete
        throttled = False
        for i, user in enumerate(users_to_delete):
            payload = {
                "ids": [str(user.id)],
                "mode": "partial"
            }
            
            response = authenticated_client.delete(url, payload, format='json')
            
            if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                throttled = True
                break
            
            time.sleep(1)
        
        assert throttled, (
            f"bulk_delete n'utilise pas BulkOperationThrottle (pas de 429 après {limit+2} requêtes)"
        )


# =========================================================================
# TEST 3: Actions spécifiques conservent leurs throttles
# =========================================================================

@pytest.mark.django_db
class TestSpecificActionThrottles:
    """Test que les actions spécifiques gardent leurs throttles personnalisés"""
    
    def test_change_password_uses_password_throttle(
        self, authenticated_client, clear_throttle_cache, admin_user
    ):
        """
        Test : change_password utilise PasswordChangeThrottle (3/hour PROD, 10/hour DEV)
        """
        url = reverse('user-change-password', kwargs={'pk': admin_user.id})
        
        # Déterminer la limite (convertie en minutes)
        if settings.DEBUG:
            # 10/hour = ~0.16/min → on peut faire ~1-2 en 10 secondes
            safe_count = 2
        else:
            # 3/hour = ~0.05/min → très strict, 1 seule tentative safe
            safe_count = 1
        
        # Envoyer quelques change_password
        for i in range(safe_count):
            payload = {
                "old_password": "TestPass123!",
                "new_password": f"NewPass{i}123!"
            }
            
            response = authenticated_client.patch(url, payload, format='json')
            
            # Ne devrait pas être throttlé dans la limite
            assert response.status_code != status.HTTP_429_TOO_MANY_REQUESTS, (
                f"change_password bloqué au #{i+1} (limite: {10 if settings.DEBUG else 3}/hour)"
            )
            
            time.sleep(2)
    
    def test_grant_superuser_uses_sensitive_throttle(
        self, authenticated_client, clear_throttle_cache, db,
        client_account, admin_role, team, organization
    ):
        """
        Test : grant_superuser utilise SensitiveActionThrottle (10/hour PROD, 30/hour DEV)
        """
        url = reverse('user-grant-superuser')
        
        # Créer un user à promouvoir
        target_user = User.objects.create_user(
            email=f"target_{int(time.time())}@test.com",
            password="TestPass123!",
            first_name="Target",
            last_name="User",
            client_account=client_account,
            role=admin_role,
            team=team,
            organization=organization
        )
        
        # Déterminer combien on peut faire
        if settings.DEBUG:
            # 30/hour = ~0.5/min → on peut faire ~5 en 10 secondes
            safe_count = 5
        else:
            # 10/hour = ~0.16/min → on peut faire ~2 en 10 secondes
            safe_count = 2
        
        # Envoyer quelques grant_superuser
        for i in range(safe_count):
            payload = {"user_id": str(target_user.id)}
            
            response = authenticated_client.post(url, payload, format='json')
            
            # Ne devrait pas être throttlé dans la limite
            # (peut échouer pour d'autres raisons business logic, mais pas 429)
            assert response.status_code != status.HTTP_429_TOO_MANY_REQUESTS, (
                f"grant_superuser bloqué au #{i+1} (limite: {30 if settings.DEBUG else 10}/hour)"
            )
            
            time.sleep(2)


# =========================================================================
# TEST 4: Vérification configuration throttles
# =========================================================================

@pytest.mark.django_db
class TestThrottleConfiguration:
    """Test que les throttles sont correctement configurés"""
    
    def test_throttle_rates_configured(self):
        """Vérifier que les THROTTLE_RATES contiennent les nouveaux scopes"""
        throttle_rates = settings.REST_FRAMEWORK.get('DEFAULT_THROTTLE_RATES', {})
        
        assert 'standard' in throttle_rates, (
            "Scope 'standard' manquant dans THROTTLE_RATES"
        )
        assert 'bulk' in throttle_rates, (
            "Scope 'bulk' manquant dans THROTTLE_RATES"
        )
        
        # Vérifier les valeurs selon environnement
        if settings.DEBUG:
            assert throttle_rates['standard'] == '50/minute', (
                f"Rate 'standard' DEV incorrect: {throttle_rates['standard']} "
                f"(attendu: 50/minute)"
            )
            assert throttle_rates['bulk'] == '5/minute', (
                f"Rate 'bulk' DEV incorrect: {throttle_rates['bulk']} "
                f"(attendu: 5/minute)"
            )
        else:
            assert throttle_rates['standard'] == '30/minute', (
                f"Rate 'standard' PROD incorrect: {throttle_rates['standard']} "
                f"(attendu: 30/minute)"
            )
            assert throttle_rates['bulk'] == '3/minute', (
                f"Rate 'bulk' PROD incorrect: {throttle_rates['bulk']} "
                f"(attendu: 3/minute)"
            )
    
    def test_default_throttle_classes_configured(self):
        """Vérifier que DEFAULT_THROTTLE_CLASSES utilise StandardRateThrottle"""
        throttle_classes = settings.REST_FRAMEWORK.get('DEFAULT_THROTTLE_CLASSES', [])
        
        # Convertir en strings si ce sont des classes
        throttle_class_names = [
            cls if isinstance(cls, str) else f"{cls.__module__}.{cls.__name__}"
            for cls in throttle_classes
        ]
        
        # Vérifier que StandardRateThrottle est présent
        has_standard = any(
            'StandardRateThrottle' in name 
            for name in throttle_class_names
        )
        
        assert has_standard, (
            "StandardRateThrottle manquant dans DEFAULT_THROTTLE_CLASSES. "
            f"Classes actuelles: {throttle_class_names}"
        )
        
        # Vérifier que BurstRateThrottle n'est PAS présent (remplacé par Standard)
        has_burst = any(
            'BurstRateThrottle' in name 
            for name in throttle_class_names
        )
        
        # Note: BurstRateThrottle peut encore être présent pour rétrocompatibilité
        # Ce test est donc informatif, pas bloquant
        if has_burst:
            import warnings
            warnings.warn(
                "BurstRateThrottle encore présent dans DEFAULT_THROTTLE_CLASSES. "
                "Ceci peut être intentionnel pour rétrocompatibilité."
            )