# backend/tests/end_users/test_client_account_tenant_isolation.py
"""
TENANT ISOLATION — ClientAccountViewSet (TD-322, Lot 0 sécurité 0.1).

The client-account endpoints used to serve EVERY tenant to ANY
authenticated user (``get_queryset`` = ``ClientAccount.objects.all()``,
no ``super()``, no module, only ``IsAuthenticated``): a user of tenant A
could list all tenants, read / rename / delete tenant B (DELETE cascades
B's users, roles, teams and organizations), create tenants, and read B's
seats / stats / users summary — whatever their role.

The endpoint is now READ-ONLY on the requester's OWN tenant:
- ``GET /client/client-accounts/<own id>/`` and ``.../seats/`` → 200
  (the real need: the admin users page's SeatsSummary);
- the same routes on another tenant's id → 404, the standard
  "not found" envelope, no data;
- list, create, update, partial update, destroy, stats and
  users-summary no longer exist (no URL name, 404 / 405 on the raw path);
- a token with no tenant (product_admin, or an end user without
  ``client_account``) gets a clean 403, never a 500.

Every case runs through the REAL endpoint (``reverse()`` + DRF client)
for the four requester profiles — individual, manager, admin and
superuser — and checks the database afterwards: tenant B, its users and
the number of client accounts are untouched (non-vacuity: B exists and
has users before the call).

DB: Postgres.
"""

import pytest
from django.urls import NoReverseMatch, reverse

from end_users.models import ClientAccount, User, UserRole
from product_admin.models import ProductAdmin

from tests.signals.conftest import (  # noqa: F401
    api,
    authenticate,
    tenant_a_id,
    tenant_b_id,
    client_account_a,
    client_account_b,
    role_individual_b,
    user_b,
)

BASE_PATH = '/client/client-accounts/'

# Requester profiles on tenant A: role flags + superuser flag.
PROFILES = {
    'individual': dict(is_admin=False, is_manager=False, is_individual=True, superuser=False),
    'manager': dict(is_admin=False, is_manager=True, is_individual=False, superuser=False),
    'admin': dict(is_admin=True, is_manager=False, is_individual=False, superuser=False),
    'superuser': dict(is_admin=True, is_manager=False, is_individual=False, superuser=True),
}

# Routes that must no longer exist (URL names removed from end_users/urls.py).
REMOVED_ROUTE_NAMES = (
    ('client:client-account-list', False),
    ('client:client-account-stats', True),
    ('client:client-account-users-summary', True),
)


@pytest.fixture(params=sorted(PROFILES))
def requester_api(request, api, authenticate, client_account_a):
    """DRF client authenticated as a tenant-A user of the given profile."""
    profile = PROFILES[request.param]
    role = UserRole.objects.create(
        client_account=client_account_a,
        name=f'Role {request.param}',
        is_admin=profile['is_admin'],
        is_manager=profile['is_manager'],
        is_individual=profile['is_individual'],
        read=True,
        write=True,
        modify=True,
        can_delete=True,
    )
    user = User.objects.create(
        email=f'{request.param}@tenant-a.test',
        client_account=client_account_a,
        role=role,
        is_active=True,
        is_superuser=profile['superuser'],
    )
    authenticate(api, user, client_account_a.id)
    return api


@pytest.fixture
def tenant_b_snapshot(client_account_b, user_b):
    """Tenant B as it is before the call — and proof it is not empty."""
    snapshot = {
        'name': client_account_b.name,
        'max_users': client_account_b.max_users,
        'is_b2b': client_account_b.is_b2b,
        'user_ids': set(
            User.objects.filter(client_account=client_account_b).values_list('id', flat=True)
        ),
        'client_accounts': ClientAccount.objects.count(),
    }
    assert snapshot['user_ids'], 'non-vacuity: tenant B must have users'
    return snapshot


def _assert_tenant_b_untouched(client_account_b, snapshot):
    assert ClientAccount.objects.count() == snapshot['client_accounts']
    b = ClientAccount.objects.get(id=client_account_b.id)
    assert (b.name, b.max_users, b.is_b2b) == (
        snapshot['name'], snapshot['max_users'], snapshot['is_b2b'],
    )
    assert set(
        User.objects.filter(client_account=b).values_list('id', flat=True)
    ) == snapshot['user_ids']


def _detail(pk):
    return reverse('client:client-account-detail', kwargs={'pk': pk})


def _seats(pk):
    return reverse('client:client-account-seats', kwargs={'pk': pk})


@pytest.mark.django_db
class TestOwnTenantStaysReadable:
    """The real need (SeatsSummary) keeps working for every profile."""

    def test_retrieve_own_tenant(self, requester_api, client_account_a):
        resp = requester_api.get(_detail(client_account_a.id))
        assert resp.status_code == 200, resp.content
        assert resp.data['id'] == str(client_account_a.id)

    def test_seats_own_tenant(self, requester_api, client_account_a):
        resp = requester_api.get(_seats(client_account_a.id))
        assert resp.status_code == 200, resp.content
        assert resp.data['data']['seats'] == client_account_a.max_users
        # The requester is the one active user of tenant A.
        assert resp.data['data']['seats_used'] == 1


@pytest.mark.django_db
class TestOtherTenantIsInvisible:

    def test_retrieve_other_tenant_is_404(
        self, requester_api, client_account_b, tenant_b_snapshot
    ):
        resp = requester_api.get(_detail(client_account_b.id))
        assert resp.status_code == 404, resp.content
        assert client_account_b.name not in str(resp.content)
        _assert_tenant_b_untouched(client_account_b, tenant_b_snapshot)

    def test_seats_other_tenant_is_404(
        self, requester_api, client_account_b, tenant_b_snapshot
    ):
        resp = requester_api.get(_seats(client_account_b.id))
        assert resp.status_code == 404, resp.content
        assert 'seats' not in str(resp.content)
        _assert_tenant_b_untouched(client_account_b, tenant_b_snapshot)


@pytest.mark.django_db
class TestRemovedRoutes:

    @pytest.mark.parametrize('name,detail', REMOVED_ROUTE_NAMES)
    def test_route_name_is_gone(self, name, detail, client_account_b):
        kwargs = {'pk': client_account_b.id} if detail else {}
        with pytest.raises(NoReverseMatch):
            reverse(name, kwargs=kwargs)

    def test_list_is_gone(self, requester_api, tenant_b_snapshot, client_account_b):
        resp = requester_api.get(BASE_PATH)
        assert resp.status_code in (404, 405), resp.content
        assert client_account_b.name not in str(resp.content)
        _assert_tenant_b_untouched(client_account_b, tenant_b_snapshot)

    def test_create_is_gone(self, requester_api, tenant_b_snapshot, client_account_b):
        resp = requester_api.post(
            BASE_PATH, {'name': 'Rogue tenant', 'max_users': 5}, format='json'
        )
        assert resp.status_code in (404, 405), resp.content
        assert not ClientAccount.objects.filter(name='Rogue tenant').exists()
        _assert_tenant_b_untouched(client_account_b, tenant_b_snapshot)

    @pytest.mark.parametrize('method', ['put', 'patch'])
    def test_update_other_tenant_is_gone(
        self, method, requester_api, client_account_b, tenant_b_snapshot
    ):
        payload = {'name': 'pwned', 'max_users': 9999, 'is_b2b': False}
        resp = getattr(requester_api, method)(
            f'{BASE_PATH}{client_account_b.id}/', payload, format='json'
        )
        assert resp.status_code in (404, 405), resp.content
        _assert_tenant_b_untouched(client_account_b, tenant_b_snapshot)

    @pytest.mark.parametrize('method', ['put', 'patch'])
    def test_update_own_tenant_is_gone(
        self, method, requester_api, client_account_a
    ):
        """Not even on its own tenant: max_users is the seat licence."""
        before = ClientAccount.objects.get(id=client_account_a.id).max_users
        resp = getattr(requester_api, method)(
            f'{BASE_PATH}{client_account_a.id}/',
            {'name': 'Tenant A Co', 'max_users': before + 1000},
            format='json',
        )
        assert resp.status_code in (404, 405), resp.content
        assert ClientAccount.objects.get(id=client_account_a.id).max_users == before

    def test_destroy_other_tenant_is_gone(
        self, requester_api, client_account_b, tenant_b_snapshot
    ):
        resp = requester_api.delete(f'{BASE_PATH}{client_account_b.id}/')
        assert resp.status_code in (404, 405), resp.content
        _assert_tenant_b_untouched(client_account_b, tenant_b_snapshot)

    @pytest.mark.parametrize('suffix', ['stats', 'users-summary'])
    def test_stats_and_users_summary_are_gone(
        self, suffix, requester_api, client_account_b, tenant_b_snapshot
    ):
        resp = requester_api.get(f'{BASE_PATH}{client_account_b.id}/{suffix}/')
        assert resp.status_code in (404, 405), resp.content
        _assert_tenant_b_untouched(client_account_b, tenant_b_snapshot)


@pytest.mark.django_db
class TestTokenWithoutTenant:
    """No tenant in the token → a clean 403, never a 500."""

    def test_product_admin_gets_403(self, api, client_account_b):
        admin = ProductAdmin.objects.create(email='ops@product.test')
        api.force_authenticate(
            user=admin,
            token={'origin': 'product_admin', 'user_id': str(admin.id), 'is_superuser': False},
        )
        for url in (_detail(client_account_b.id), _seats(client_account_b.id)):
            resp = api.get(url)
            assert resp.status_code == 403, (url, resp.content)
            assert 'error' in resp.data

    def test_end_user_without_client_account_gets_403(
        self, api, client_account_b, user_b
    ):
        api.force_authenticate(
            user=user_b,
            token={'origin': 'end_users', 'user_id': str(user_b.id), 'client_account': None},
        )
        resp = api.get(_detail(client_account_b.id))
        assert resp.status_code == 403, resp.content
        assert 'error' in resp.data
