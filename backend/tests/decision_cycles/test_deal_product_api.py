# tests/decision_cycles/test_deal_product_api.py
"""
Integration tests for DealProduct API endpoints nested under a DecisionCycle.

Covers CRUD, context injection, uniqueness, and cross-tenant/cross-cycle
isolation via _resolve_parent_cycle scoping.
"""

import uuid

import pytest
from rest_framework import status


def _products_url(cycle_id):
    return f'/decision-cycles/{cycle_id}/products/'


def _product_detail_url(cycle_id, product_id):
    return f'/decision-cycles/{cycle_id}/products/{product_id}/'


# =============================================================================
# CREATE
# =============================================================================


@pytest.mark.django_db
class TestDealProductCreate:

    def test_create_product(self, authed_api_a, cycle, product_catalog_entry):
        resp = authed_api_a.post(
            _products_url(cycle.id),
            {
                'product_catalog_entry': str(product_catalog_entry.id),
                'quantity': 5,
                'unit_price': '8000.00',
                'notes': 'Discounted rate',
            },
            format='json',
        )
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()['data']
        assert data['quantity'] == 5
        assert data['product_catalog_entry'] == str(product_catalog_entry.id)

    def test_create_duplicate_product_fails(
        self, authed_api_a, cycle, product_catalog_entry, deal_product
    ):
        resp = authed_api_a.post(
            _products_url(cycle.id),
            {
                'product_catalog_entry': str(product_catalog_entry.id),
                'quantity': 1,
            },
            format='json',
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_on_nonexistent_cycle_returns_404(
        self, authed_api_a, product_catalog_entry
    ):
        fake_cycle_id = uuid.uuid4()
        resp = authed_api_a.post(
            _products_url(fake_cycle_id),
            {
                'product_catalog_entry': str(product_catalog_entry.id),
                'quantity': 1,
            },
            format='json',
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND


# =============================================================================
# LIST / RETRIEVE
# =============================================================================


@pytest.mark.django_db
class TestDealProductRead:

    def test_list_products(self, authed_api_a, cycle, deal_product):
        resp = authed_api_a.get(_products_url(cycle.id))
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()['data']
        assert len(data) == 1
        assert data[0]['id'] == str(deal_product.id)

    def test_retrieve_product(self, authed_api_a, cycle, deal_product):
        resp = authed_api_a.get(_product_detail_url(cycle.id, deal_product.id))
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()['data']['id'] == str(deal_product.id)

    def test_list_empty_cycle(self, authed_api_a, cycle):
        resp = authed_api_a.get(_products_url(cycle.id))
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()['data'] == []


# =============================================================================
# UPDATE
# =============================================================================


@pytest.mark.django_db
class TestDealProductUpdate:

    def test_patch_quantity(self, authed_api_a, cycle, deal_product):
        resp = authed_api_a.patch(
            _product_detail_url(cycle.id, deal_product.id),
            {'quantity': 10},
            format='json',
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()['data']['quantity'] == 10

    def test_patch_unit_price_null(self, authed_api_a, cycle, deal_product):
        resp = authed_api_a.patch(
            _product_detail_url(cycle.id, deal_product.id),
            {'unit_price': None},
            format='json',
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()['data']['unit_price'] is None


# =============================================================================
# DELETE
# =============================================================================


@pytest.mark.django_db
class TestDealProductDelete:

    def test_delete_product(self, authed_api_a, cycle, deal_product):
        resp = authed_api_a.delete(_product_detail_url(cycle.id, deal_product.id))
        assert resp.status_code == status.HTTP_204_NO_CONTENT

        resp = authed_api_a.get(_products_url(cycle.id))
        assert len(resp.json()['data']) == 0


# =============================================================================
# ISOLATION — cross-cycle and cross-tenant
# =============================================================================


@pytest.mark.django_db
class TestDealProductIsolation:

    def test_product_not_visible_from_other_cycle(
        self, authed_api_a, cycle, deal_product, account, user_a
    ):
        from app_modules.decision_cycles.models import DecisionCycle
        other_cycle = DecisionCycle(
            account=account, owner=user_a, name='Other Cycle', is_active=False,
        )
        other_cycle.save(user=user_a, client_id=account.client_id)

        resp = authed_api_a.get(_products_url(other_cycle.id))
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()['data'] == []

    def test_tenant_b_cannot_access_tenant_a_products(
        self, authed_api_b, cycle, deal_product
    ):
        resp = authed_api_b.get(_products_url(cycle.id))
        assert resp.status_code == status.HTTP_404_NOT_FOUND
