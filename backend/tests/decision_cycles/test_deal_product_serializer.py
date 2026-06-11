# tests/decision_cycles/test_deal_product_serializer.py
"""
Tests for DealProduct serializers (Create / Update / List).

Validates:
  - validators=[] bypasses DRF auto-generated UniqueTogetherValidator
  - decision_cycle injected from context (not a serializer field)
  - client_id injected from JWT context
  - validate_client_scoped_uniqueness enforces (dc, product) uniqueness
  - DealProductListSerializer exposes line_total and product detail
"""

import pytest
from unittest.mock import MagicMock

from app_modules.decision_cycles.serializers import (
    DealProductCreateSerializer,
    DealProductUpdateSerializer,
    DealProductListSerializer,
)


pytestmark = pytest.mark.django_db


# =============================================================================
# HELPERS
# =============================================================================

def _make_request_context(user, client_id, decision_cycle=None):
    """Build a serializer context dict mirroring what a ViewSet provides."""
    request = MagicMock()
    request.user = user
    request.auth = {
        'client_id': str(client_id),
    }
    ctx = {
        'request': request,
        'client_id': str(client_id),
    }
    if decision_cycle is not None:
        ctx['decision_cycle'] = decision_cycle
    return ctx


# =============================================================================
# CREATE SERIALIZER
# =============================================================================

class TestDealProductCreateSerializer:

    def test_validators_list_is_empty(self):
        assert DealProductCreateSerializer.Meta.validators == []

    def test_decision_cycle_not_in_fields(self):
        assert 'decision_cycle' not in DealProductCreateSerializer.Meta.fields

    def test_valid_create(self, cycle, product_catalog_entry, user_a):
        ctx = _make_request_context(user_a, cycle.client_id, decision_cycle=cycle)
        data = {
            'product_catalog_entry': product_catalog_entry.id,
            'quantity': 3,
            'unit_price': '8500.00',
            'notes': 'Volume discount',
        }
        serializer = DealProductCreateSerializer(data=data, context=ctx)
        assert serializer.is_valid(), serializer.errors
        instance = serializer.save()
        assert instance.decision_cycle_id == cycle.id
        assert instance.quantity == 3

    def test_create_without_decision_cycle_context_fails(
        self, cycle, product_catalog_entry, user_a,
    ):
        ctx = _make_request_context(user_a, cycle.client_id, decision_cycle=None)
        data = {'product_catalog_entry': product_catalog_entry.id}
        serializer = DealProductCreateSerializer(data=data, context=ctx)
        assert not serializer.is_valid()

    def test_duplicate_product_on_same_cycle_fails(
        self, cycle, product_catalog_entry, user_a, deal_product,
    ):
        ctx = _make_request_context(user_a, cycle.client_id, decision_cycle=cycle)
        data = {'product_catalog_entry': product_catalog_entry.id}
        serializer = DealProductCreateSerializer(data=data, context=ctx)
        assert not serializer.is_valid()

    def test_same_product_different_cycle_succeeds(
        self, cycle, product_catalog_entry, user_a, deal_product, account,
    ):
        from app_modules.decision_cycles.models import DecisionCycle
        cycle2 = DecisionCycle(
            account=account, owner=user_a, name='Cycle 2', is_active=False,
        )
        cycle2.save(user=user_a, client_id=account.client_id)

        ctx = _make_request_context(user_a, cycle2.client_id, decision_cycle=cycle2)
        data = {'product_catalog_entry': product_catalog_entry.id, 'quantity': 1}
        serializer = DealProductCreateSerializer(data=data, context=ctx)
        assert serializer.is_valid(), serializer.errors

    def test_default_quantity_is_one(self, cycle, product_catalog_entry, user_a):
        ctx = _make_request_context(user_a, cycle.client_id, decision_cycle=cycle)
        data = {'product_catalog_entry': product_catalog_entry.id}
        serializer = DealProductCreateSerializer(data=data, context=ctx)
        assert serializer.is_valid(), serializer.errors
        instance = serializer.save()
        assert instance.quantity == 1


# =============================================================================
# UPDATE SERIALIZER
# =============================================================================

class TestDealProductUpdateSerializer:

    def test_validators_list_is_empty(self):
        assert DealProductUpdateSerializer.Meta.validators == []

    def test_product_catalog_entry_not_in_fields(self):
        assert 'product_catalog_entry' not in DealProductUpdateSerializer.Meta.fields

    def test_update_quantity(self, deal_product, user_a):
        ctx = _make_request_context(user_a, deal_product.client_id)
        data = {'quantity': 10}
        serializer = DealProductUpdateSerializer(
            instance=deal_product, data=data, partial=True, context=ctx,
        )
        assert serializer.is_valid(), serializer.errors
        updated = serializer.save()
        assert updated.quantity == 10

    def test_update_unit_price_to_null(self, deal_product, user_a):
        ctx = _make_request_context(user_a, deal_product.client_id)
        data = {'unit_price': None}
        serializer = DealProductUpdateSerializer(
            instance=deal_product, data=data, partial=True, context=ctx,
        )
        assert serializer.is_valid(), serializer.errors
        updated = serializer.save()
        assert updated.unit_price is None


# =============================================================================
# LIST SERIALIZER
# =============================================================================

class TestDealProductListSerializer:

    def test_line_total_exposed(self, deal_product):
        serializer = DealProductListSerializer(deal_product)
        data = serializer.data
        assert 'line_total' in data
        expected = deal_product.quantity * deal_product.unit_price
        assert float(data['line_total']) == float(expected)

    def test_product_catalog_entry_detail(self, deal_product):
        serializer = DealProductListSerializer(deal_product)
        detail = serializer.data['product_catalog_entry_detail']
        assert detail is not None
        assert detail['name'] == deal_product.product_catalog_entry.name
        assert 'default_unit_price' in detail
