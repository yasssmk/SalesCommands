# backend/tests/product_catalog/test_seller_profile_api.py
"""
Sprint 2 Game Plan — sub-step G6 (PO decision Q6): the SELLER profile, one
per tenant — what the Game Plan knows of the company that sells.

Model product_catalog.SellerProfile, 1-1 with the tenant (client_id unique):
company description, global value proposition, customer references (name,
sector, result), credibility figures and certifications, main competitors
and positioning, ideal targets (sectors, sizes, roles). No field is
required; the maximum lengths are constants (product_catalog/constants.py).

Endpoint GET / PUT /product-catalog/seller-profile/ — the requester's OWN
tenant:
  * GET: any user of the tenant; an empty profile (id null) when none yet;
  * PUT: the ADMIN only, created on the first PUT, updated afterwards (one
    row per tenant); a manager / an individual -> 403 — the module's registry
    (update: admin only), enforced at the gate because product_catalog is
    enabled in salescommands/settings.py PERMISSIONS_CONFIG['MODULES']
    (non-vacuity: opening the registry's update to the individual tier turns
    the refusal red);
  * another method -> 405 (http_method_names, TD-330);
  * tenant A never sees B's profile; the queryset goes through the shared
    tenant filter (super().get_queryset(), the get_queryset guardrail).

DB: Postgres.
"""

import pytest
from rest_framework.test import APIClient

from app_modules.product_catalog.constants import (
    SELLER_PROFILE_REFERENCE_FIELD_MAX_CHARS,
    SELLER_PROFILE_REFERENCES_MAX,
    SELLER_PROFILE_TEXT_MAX_CHARS,
)


pytestmark = pytest.mark.django_db

URL = '/product-catalog/seller-profile/'

PROFILE = {
    'company_description': 'aphoriQ builds an AI-native CRM for B2B sales teams.',
    'value_proposition': 'Every deal prepared like by your best AE.',
    'customer_references': [
        {'name': 'Logistix', 'sector': 'Logistics', 'result': 'Forecast accuracy up 20 points.'},
    ],
    'credibility_and_certifications': 'ISO 27001. 120 customers in Europe.',
    'competitors_and_positioning': 'Versus generic CRMs: the conversation, not the data entry.',
    'ideal_targets': 'B2B software and services, 50-500 employees, sales leaders.',
}
TEXT_FIELDS = (
    'company_description', 'value_proposition', 'credibility_and_certifications',
    'competitors_and_positioning', 'ideal_targets',
)


# =============================================================================
# FIXTURES
# =============================================================================

def _user(client_account, email, *, admin=False, manager=False):
    from end_users.models import User, UserRole
    if admin:
        role = UserRole.objects.get(client_account=client_account, name='Admin')
    else:
        role = UserRole.objects.create(
            client_account=client_account, name='Manager' if manager else 'Rep',
            is_admin=False, is_manager=manager, is_individual=not manager,
            read=True, write=True, modify=True, can_delete=True,
        )
    return User.objects.create(email=email, client_account=client_account, role=role, is_active=True)


@pytest.fixture
def client_as(authenticate):
    def _client(user):
        client = APIClient(enforce_csrf_checks=False)
        authenticate(client, user, user.client_account_id)
        return client
    return _client


@pytest.fixture
def admin_a(client_account_a):
    return _user(client_account_a, 'admin@tenant-a.test', admin=True)


@pytest.fixture
def admin_b(client_account_b):
    return _user(client_account_b, 'admin@tenant-b.test', admin=True)


def _data(resp):
    body = resp.json()
    return body.get('data', body)


# =============================================================================
# WRITE — the admin only (a real 403 for the others)
# =============================================================================

@pytest.mark.parametrize('manager', [False, True], ids=['individual', 'manager'])
def test_a_non_admin_cannot_write_the_profile(manager, client_as, client_account_a):
    from app_modules.product_catalog.models import SellerProfile
    user = _user(client_account_a, f'user-{manager}@tenant-a.test', manager=manager)

    resp = client_as(user).put(URL, PROFILE, format='json')

    assert resp.status_code == 403, resp.content
    assert not SellerProfile.objects.exists()


def test_the_admin_creates_then_updates_the_one_profile(client_as, admin_a, client_account_a):
    from app_modules.product_catalog.models import SellerProfile
    client = client_as(admin_a)

    created = client.put(URL, PROFILE, format='json')
    assert created.status_code == 200, created.content
    updated = client.put(URL, {**PROFILE, 'value_proposition': 'Win more, prepare less.'},
                         format='json')
    assert updated.status_code == 200, updated.content

    [row] = SellerProfile.objects.all()
    assert row.client_id == client_account_a.id
    assert row.value_proposition == 'Win more, prepare less.'
    assert row.customer_references == PROFILE['customer_references']
    assert _data(updated)['id'] == str(row.id) == _data(created)['id']


def test_no_field_is_required(client_as, admin_a):
    resp = client_as(admin_a).put(URL, {}, format='json')

    assert resp.status_code == 200, resp.content
    data = _data(resp)
    assert all(data[field] == '' for field in TEXT_FIELDS)
    assert data['customer_references'] == []


# =============================================================================
# READ — any user of the tenant; an empty profile when none
# =============================================================================

def test_without_a_profile_the_read_is_an_empty_profile(client_as, client_account_a):
    user = _user(client_account_a, 'rep@tenant-a.test')

    resp = client_as(user).get(URL)

    assert resp.status_code == 200, resp.content
    data = _data(resp)
    assert data['id'] is None
    assert all(data[field] == '' for field in TEXT_FIELDS)
    assert data['customer_references'] == []


def test_any_user_of_the_tenant_reads_the_profile(client_as, admin_a, client_account_a):
    client_as(admin_a).put(URL, PROFILE, format='json')
    user = _user(client_account_a, 'rep@tenant-a.test')

    data = _data(client_as(user).get(URL))

    assert data['company_description'] == PROFILE['company_description']
    assert data['customer_references'] == PROFILE['customer_references']


# =============================================================================
# TENANT ISOLATION
# =============================================================================

def test_a_tenant_never_sees_the_profile_of_another(client_as, admin_a, admin_b):
    from app_modules.product_catalog.models import SellerProfile
    client_as(admin_b).put(URL, PROFILE, format='json')

    data_a = _data(client_as(admin_a).get(URL))
    assert data_a['id'] is None
    assert data_a['company_description'] == ''

    client_as(admin_a).put(URL, {'company_description': 'Tenant A.'}, format='json')
    assert SellerProfile.objects.count() == 2
    assert _data(client_as(admin_b).get(URL))['company_description'] == PROFILE['company_description']


# =============================================================================
# VALIDATION — the bounds (constants)
# =============================================================================

def test_a_text_above_its_bound_is_refused(client_as, admin_a):
    resp = client_as(admin_a).put(
        URL, {'company_description': 'x' * (SELLER_PROFILE_TEXT_MAX_CHARS + 1)}, format='json')

    assert resp.status_code == 400, resp.content


@pytest.mark.parametrize('references', [
    'not a list',
    [{'name': 'Logistix', 'unknown': 'x'}],
    [{'name': 'x' * (SELLER_PROFILE_REFERENCE_FIELD_MAX_CHARS + 1)}],
    [{'name': f'Customer {i}'} for i in range(SELLER_PROFILE_REFERENCES_MAX + 1)],
    [{'name': 42}],
], ids=['not_a_list', 'unknown_key', 'too_long', 'too_many', 'not_a_string'])
def test_invalid_references_are_refused(references, client_as, admin_a):
    resp = client_as(admin_a).put(URL, {'customer_references': references}, format='json')

    assert resp.status_code == 400, resp.content


# =============================================================================
# METHODS — GET / PUT only (TD-330)
# =============================================================================

@pytest.mark.parametrize('method', ['post', 'patch', 'delete'])
def test_another_method_is_not_allowed(method, client_as, admin_a):
    resp = getattr(client_as(admin_a), method)(URL, PROFILE, format='json')

    assert resp.status_code == 405, resp.content
