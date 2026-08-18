# backend/tests/decision_cycles/test_deal_product_discount_bounds.py
"""
TD-74 — discount_percent is bounded to [0, 100], at BOTH levels.

Why it is load-bearing: the discount drives the read-time derived amount
(quantity x price x (1 - discount/100)), so an out-of-range value silently
corrupts the line, the cycle's total_deal_value AND KPI 7 — a >100% discount
turns a deal NEGATIVE.

Two guards, tested through their real paths:

* API (DRF) — ``validate_discount_percent_range`` in serializers.py gives a
  clean business-rule 400 before the DB is touched. Endpoint tests mirror
  tests/decision_cycles/test_deal_product_api.py (same URL helpers, same
  authed_api_a fixture).
* DB (CheckConstraint ``deal_product_discount_percent_bounds``) — the backstop
  for every write path that never sees a serializer: shell, import, data
  migration. Tested by saving the model directly, mirroring the IntegrityError
  assertion in tests/decision_cycles/test_deal_product.py:70-89.

The two are independent on purpose: neither alone covers the other's path.
"""

from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from rest_framework import status

from app_modules.decision_cycles.models import DealProduct


pytestmark = pytest.mark.django_db


def _products_url(cycle_id):
    return f'/decision_cycles/{cycle_id}/products/'


def _product_detail_url(cycle_id, product_id):
    return f'/decision_cycles/{cycle_id}/products/{product_id}/'


ACCEPTED = ['0', '0.01', '50', '99.99', '100']
REJECTED = ['-0.01', '-1', '-10', '100.01', '101', '150']


# =============================================================================
# API — clean 400, never a leaked IntegrityError
# =============================================================================

class TestCreateDiscountBounds:

    @pytest.mark.parametrize('discount', REJECTED)
    def test_out_of_range_discount_is_rejected_with_400(
        self, authed_api_a, cycle, product_catalog_entry, discount,
    ):
        resp = authed_api_a.post(
            _products_url(cycle.id),
            {
                'product_catalog_entry': str(product_catalog_entry.id),
                'quantity': 1,
                'unit_price': '10000.00',
                'discount_percent': discount,
            },
            format='json',
        )

        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert not DealProduct.objects.filter(decision_cycle=cycle).exists()

    @pytest.mark.parametrize('discount', ACCEPTED)
    def test_in_range_discount_is_accepted(
        self, authed_api_a, cycle, product_catalog_entry, discount,
    ):
        resp = authed_api_a.post(
            _products_url(cycle.id),
            {
                'product_catalog_entry': str(product_catalog_entry.id),
                'quantity': 1,
                'unit_price': '10000.00',
                'discount_percent': discount,
            },
            format='json',
        )

        assert resp.status_code == status.HTTP_201_CREATED
        assert Decimal(resp.json()['data']['discount_percent']) == Decimal(discount)

    def test_the_error_names_the_offending_rule(
        self, authed_api_a, cycle, product_catalog_entry,
    ):
        """A business-rule message, not a database error string."""
        resp = authed_api_a.post(
            _products_url(cycle.id),
            {
                'product_catalog_entry': str(product_catalog_entry.id),
                'quantity': 1,
                'discount_percent': '150',
            },
            format='json',
        )

        body = str(resp.json()).lower()
        assert 'discount_percent' in body
        assert '0 and 100' in body
        assert 'integrityerror' not in body
        assert 'constraint' not in body

    def test_discount_defaults_to_zero_when_omitted(
        self, authed_api_a, cycle, product_catalog_entry,
    ):
        resp = authed_api_a.post(
            _products_url(cycle.id),
            {'product_catalog_entry': str(product_catalog_entry.id), 'quantity': 1},
            format='json',
        )

        assert resp.status_code == status.HTTP_201_CREATED
        assert Decimal(resp.json()['data']['discount_percent']) == Decimal('0')


class TestUpdateDiscountBounds:

    @pytest.mark.parametrize('discount', REJECTED)
    def test_patching_out_of_range_is_rejected_and_persists_nothing(
        self, authed_api_a, cycle, deal_product, discount,
    ):
        resp = authed_api_a.patch(
            _product_detail_url(cycle.id, deal_product.id),
            {'discount_percent': discount},
            format='json',
        )

        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        deal_product.refresh_from_db()
        assert deal_product.discount_percent == Decimal('0')

    def test_patching_a_valid_discount_updates_the_derived_amount(
        self, authed_api_a, cycle, deal_product,
    ):
        """The guard does not get in the way of the feature it protects:
        a legal discount flows straight into the derived amounts."""
        resp = authed_api_a.patch(
            _product_detail_url(cycle.id, deal_product.id),
            {'discount_percent': '25'},
            format='json',
        )

        assert resp.status_code == status.HTTP_200_OK
        deal_product.refresh_from_db()
        assert deal_product.discount_percent == Decimal('25')
        # fixture line: 2 x 9500 = 19000, minus 25% -> 14250
        assert deal_product.line_total == Decimal('14250')
        assert cycle.total_deal_value == Decimal('14250')
        assert Decimal(resp.json()['data']['line_total']) == Decimal('14250')


# =============================================================================
# DB — the backstop for non-API writes
# =============================================================================

class TestDatabaseConstraint:

    @pytest.mark.parametrize('discount', ['-1', '150'])
    def test_direct_save_out_of_range_raises_integrity_error(
        self, cycle, product_catalog_entry, user_a, discount,
    ):
        line = DealProduct(
            decision_cycle=cycle,
            product_catalog_entry=product_catalog_entry,
            quantity=1,
            unit_price=Decimal('10000'),
            discount_percent=Decimal(discount),
        )

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                line.save(user=user_a, client_id=cycle.client_id)

    @pytest.mark.parametrize('discount', ['0', '100'])
    def test_direct_save_at_the_bounds_is_allowed(
        self, cycle, product_catalog_entry, user_a, discount,
    ):
        """Inclusive on both ends — 100% off is a legal (free) line."""
        line = DealProduct(
            decision_cycle=cycle,
            product_catalog_entry=product_catalog_entry,
            quantity=1,
            unit_price=Decimal('10000'),
            discount_percent=Decimal(discount),
        )
        line.save(user=user_a, client_id=cycle.client_id)

        assert line.pk is not None
        assert line.line_total == (
            Decimal('0') if discount == '100' else Decimal('10000')
        )

    def test_bulk_update_cannot_slip_past_the_constraint(
        self, cycle, deal_product,
    ):
        """queryset.update() bypasses save() and every serializer — exactly the
        path the DB constraint exists for."""
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                DealProduct.objects.filter(pk=deal_product.pk).update(
                    discount_percent=Decimal('150')
                )

    def test_the_constraint_is_declared_on_the_model(self):
        names = {c.name for c in DealProduct._meta.constraints}
        assert 'deal_product_discount_percent_bounds' in names
