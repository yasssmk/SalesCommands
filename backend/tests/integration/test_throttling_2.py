# tests/integration/test_throttling_2F.py
"""
Tests d'intégration Phase 2.F : Throttle réaliste

Valide :
1. StandardRateThrottle sur GET endpoints (30/min PROD, 50/min DEV)
2. BulkOperationThrottle sur bulk operations (3/min PROD, 5/min DEV)
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
        name="Test Client Throttle",
        is_b2b=True,
        max_users=100
    )


@pytest.fixture
def admin_role(db, client_account):
    """Get or create admin role (auto-created by ClientAccount signal)"""
    role, created = UserRole.objects.get_or_create(
        name="Admin",
        client_account=client_account,
        defaults={
            'read': True,
            'write': True,
            'modify': True,
            'delete': True
        }
    )
    return role


@pytest.fixture
def organization(db, client_account):
    """Create test organization"""
    return Organization.objects.create(
        name="Test Org Throttle",
        client_account=client_account
    )


@pytest.fixture
def team(db, organization):
    """Create test team"""
    return Team.objects.create(
        name="Test Team Throttle",
        organization=organization
    )


@pytest.fixture
def admin_user(db, client_account, admin_role, team, organization):
    """Create admin user for tests"""
    user = User.objects.create_user(
        email=f"admin_throttle_{int(time.time())}@test.com",
        password="TestPass123!",
        first_name="Admin",
        last_name="Throttle",
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
    """Test StandardRateThrottle (30/min PROD, 50/min DEV)"""
    
    def test_get_users_list_not_throttled_under_limit(
        self, authenticated_client, clear_throttle_cache
    ):
        """5 GET requests should not be throttled"""
        url = reverse('client:user-list')
        
        for i in range(5):
            response = authenticated_client.get(url)
            assert response.status_code != status.HTTP_429_TOO_MANY_REQUESTS, (
                f"Request #{i+1} was throttled (429)"
            )
            time.sleep(0.2)


# =========================================================================
# TEST 2: BulkOperationThrottle sur bulk operations
# =========================================================================

@pytest.mark.django_db
class TestBulkOperationThrottle:
    """Test BulkOperationThrottle (3/min PROD, 5/min DEV)"""
    
    def test_bulk_create_not_throttled_under_limit(
        self, authenticated_client, clear_throttle_cache, admin_role, team, organization
    ):
        """2-3 bulk operations should not be throttled"""
        url = reverse('client:user-bulk-create')
        
        # Safe count according to environment
        safe_count = 2  # Conservative: works in both PROD and DEV
        
        for i in range(safe_count):
            payload = {
                "users": [{
                    "email": f"bulk_{i}_{int(time.time())}@test.com",
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
                f"Bulk #{i+1} was throttled (429)"
            )
            time.sleep(1)


# =========================================================================
# TEST 3: Configuration throttles
# =========================================================================

@pytest.mark.django_db
class TestThrottleConfiguration:
    """Test throttle configuration"""
    
    def test_throttle_rates_configured(self):
        """Verify THROTTLE_RATES contains new scopes"""
        throttle_rates = settings.REST_FRAMEWORK.get('DEFAULT_THROTTLE_RATES', {})
        
        assert 'standard' in throttle_rates, "Scope 'standard' missing"
        assert 'bulk' in throttle_rates, "Scope 'bulk' missing"
        
        # Check values
        if settings.DEBUG:
            assert throttle_rates['standard'] == '50/minute'
            assert throttle_rates['bulk'] == '5/minute'
        else:
            assert throttle_rates['standard'] == '30/minute'
            assert throttle_rates['bulk'] == '3/minute'
    
    def test_default_throttle_classes_configured(self):
        """Verify DEFAULT_THROTTLE_CLASSES uses StandardRateThrottle"""
        throttle_classes = settings.REST_FRAMEWORK.get('DEFAULT_THROTTLE_CLASSES', [])
        
        throttle_class_names = [
            cls if isinstance(cls, str) else f"{cls.__module__}.{cls.__name__}"
            for cls in throttle_classes
        ]
        
        has_standard = any(
            'StandardRateThrottle' in name 
            for name in throttle_class_names
        )
        
        assert has_standard, (
            f"StandardRateThrottle missing. Classes: {throttle_class_names}"
        )