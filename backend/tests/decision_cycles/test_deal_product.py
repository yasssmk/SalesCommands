# backend/tests/decision_cycles/test_deal_product.py
"""
Model-level tests for DealProduct.
"""

import pytest
from decimal import Decimal
from django.db import IntegrityError


pytestmark = pytest.mark.django_db


class TestDealProductCreate:

    def test_create_with_override_price(self, deal_product):
        assert deal_product.pk is not None
        assert deal_product.quantity == 2
        assert deal_product.unit_price == Decimal('9500')

    def test_create_without_override(self, cycle, product_catalog_entry, user_a):
        from app_modules.decision_cycles.models import DealProduct

        dp = DealProduct(
            decision_cycle=cycle,
            product_catalog_entry=product_catalog_entry,
            quantity=3,
        )
        dp.save(user=user_a, client_id=cycle.client_id)

        assert dp.unit_price is None


class TestDealProductLineTotal:

    def test_line_total_with_override(self, deal_product):
        assert deal_product.line_total == Decimal('19000')

    def test_line_total_falls_back_to_catalog(
        self, cycle, product_catalog_entry, user_a
    ):
        from app_modules.decision_cycles.models import DealProduct

        dp = DealProduct(
            decision_cycle=cycle,
            product_catalog_entry=product_catalog_entry,
            quantity=5,
        )
        dp.save(user=user_a, client_id=cycle.client_id)

        assert dp.line_total == Decimal('50000')

    def test_line_total_zero_when_no_price(self, cycle, user_a, client_account_a):
        from app_modules.decision_cycles.models import DealProduct
        from app_modules.product_catalog.models import ProductCatalog

        no_price = ProductCatalog(name='Free Tier')
        no_price.save(user=user_a, client_id=client_account_a.id)

        dp = DealProduct(
            decision_cycle=cycle,
            product_catalog_entry=no_price,
            quantity=1,
        )
        dp.save(user=user_a, client_id=cycle.client_id)

        assert dp.line_total == 0


class TestDealProductUniqueness:

    def test_unique_per_cycle_and_product(
        self, cycle, product_catalog_entry, user_a
    ):
        from app_modules.decision_cycles.models import DealProduct

        DealProduct(
            decision_cycle=cycle,
            product_catalog_entry=product_catalog_entry,
            quantity=1,
        ).save(user=user_a, client_id=cycle.client_id)

        dup = DealProduct(
            decision_cycle=cycle,
            product_catalog_entry=product_catalog_entry,
            quantity=2,
        )
        with pytest.raises(IntegrityError):
            dup.save(user=user_a, client_id=cycle.client_id)


class TestDealProductProtect:

    def test_protect_on_catalog_delete(self, deal_product, product_catalog_entry):
        from django.db.models import ProtectedError

        with pytest.raises(ProtectedError):
            product_catalog_entry.delete()


class TestDealProductStr:

    def test_str(self, deal_product):
        s = str(deal_product)
        assert 'Enterprise License' in s
        assert 'x2' in s
