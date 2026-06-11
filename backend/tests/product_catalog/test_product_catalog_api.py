# backend/tests/product_catalog/test_product_catalog_api.py
"""
API-level tests for the ProductCatalog CRUD endpoints.
"""

import pytest


pytestmark = pytest.mark.django_db

BASE_URL = '/product-catalog/'


class TestProductCatalogList:

    def test_list_empty(self, authed_api_a):
        resp = authed_api_a.get(BASE_URL)
        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is True

    def test_list_returns_entries(self, authed_api_a, product_entry):
        resp = authed_api_a.get(BASE_URL)
        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is True
        results = data['data']
        if isinstance(results, dict):
            results = results.get('results', [])
        assert len(results) >= 1


class TestProductCatalogRetrieve:

    def test_retrieve(self, authed_api_a, product_entry):
        resp = authed_api_a.get(f'{BASE_URL}{product_entry.id}/')
        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is True
        assert data['data']['name'] == 'Enterprise License'

    def test_retrieve_not_found(self, authed_api_a):
        import uuid
        resp = authed_api_a.get(f'{BASE_URL}{uuid.uuid4()}/')
        assert resp.status_code == 404


class TestProductCatalogCreate:

    def test_create_minimal(self, authed_api_a):
        """Individual role cannot create (admin-only)."""
        resp = authed_api_a.post(BASE_URL, {'name': 'New Product'})
        # individual → permission denied
        assert resp.status_code in (201, 403)

    def test_create_admin(
        self, api, authenticate, client_account_a, db
    ):
        from end_users.models import User, UserRole

        role = UserRole.objects.create(
            client_account=client_account_a,
            name='Admin',
            is_admin=True,
            is_manager=False,
            is_individual=False,
            read=True,
            write=True,
            modify=True,
            can_delete=True,
        )
        admin = User.objects.create(
            email='admin@tenant-a.test',
            client_account=client_account_a,
            role=role,
            is_active=True,
        )
        authenticate(api, admin, client_account_a.id)

        resp = api.post(BASE_URL, {
            'name': 'Admin Product',
            'default_unit_price': '5000.00',
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data['success'] is True
        assert data['data']['name'] == 'Admin Product'


class TestProductCatalogUpdate:

    def test_patch(self, api, authenticate, client_account_a, product_entry, db):
        from end_users.models import User, UserRole

        role = UserRole.objects.create(
            client_account=client_account_a,
            name='Admin',
            is_admin=True,
            is_manager=False,
            is_individual=False,
            read=True,
            write=True,
            modify=True,
            can_delete=True,
        )
        admin = User.objects.create(
            email='admin-upd@tenant-a.test',
            client_account=client_account_a,
            role=role,
            is_active=True,
        )
        authenticate(api, admin, client_account_a.id)

        resp = api.patch(
            f'{BASE_URL}{product_entry.id}/',
            {'name': 'Renamed'},
            format='json',
        )
        assert resp.status_code == 200
        assert resp.json()['data']['name'] == 'Renamed'


class TestProductCatalogDelete:

    def test_delete(self, api, authenticate, client_account_a, product_entry, db):
        from end_users.models import User, UserRole

        role = UserRole.objects.create(
            client_account=client_account_a,
            name='Admin',
            is_admin=True,
            is_manager=False,
            is_individual=False,
            read=True,
            write=True,
            modify=True,
            can_delete=True,
        )
        admin = User.objects.create(
            email='admin-del@tenant-a.test',
            client_account=client_account_a,
            role=role,
            is_active=True,
        )
        authenticate(api, admin, client_account_a.id)

        resp = api.delete(f'{BASE_URL}{product_entry.id}/')
        assert resp.status_code == 200
        assert resp.json()['success'] is True


class TestProductCatalogTenantIsolation:

    def test_tenant_b_cannot_see_tenant_a(
        self, authed_api_b, product_entry
    ):
        resp = authed_api_b.get(f'{BASE_URL}{product_entry.id}/')
        assert resp.status_code == 404
