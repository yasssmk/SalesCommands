# backend/tests/product_catalog/test_product_catalog_model.py
"""
Model-level tests for ProductCatalog.
"""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError


pytestmark = pytest.mark.django_db


class TestProductCatalogCreate:

    def test_create_minimal(self, client_account_a, user_a):
        from app_modules.product_catalog.models import ProductCatalog

        entry = ProductCatalog(name='Basic Plan')
        entry.save(user=user_a, client_id=client_account_a.id)

        assert entry.pk is not None
        assert entry.name == 'Basic Plan'
        assert entry.description == ''
        assert entry.value_proposition == ''
        assert entry.default_unit_price is None
        assert entry.client_id == client_account_a.id

    def test_create_full(self, client_account_a, user_a):
        from app_modules.product_catalog.models import ProductCatalog
        from decimal import Decimal

        entry = ProductCatalog(
            name='Pro Plan',
            description='Professional tier',
            value_proposition='Increased productivity',
            default_unit_price=Decimal('5000.00'),
        )
        entry.save(user=user_a, client_id=client_account_a.id)

        assert entry.default_unit_price == Decimal('5000.00')
        assert str(entry) == 'Pro Plan'


class TestProductCatalogClean:

    def test_clean_strips_name(self, client_account_a, user_a):
        from app_modules.product_catalog.models import ProductCatalog

        entry = ProductCatalog(name='  Padded Name  ')
        entry.clean()
        assert entry.name == 'Padded Name'

    def test_clean_rejects_blank_name(self):
        from app_modules.product_catalog.models import ProductCatalog

        entry = ProductCatalog(name='')
        with pytest.raises(ValidationError) as exc_info:
            entry.clean()
        assert 'name' in exc_info.value.message_dict

    def test_clean_rejects_whitespace_only_name(self):
        from app_modules.product_catalog.models import ProductCatalog

        entry = ProductCatalog(name='   ')
        with pytest.raises(ValidationError) as exc_info:
            entry.clean()
        assert 'name' in exc_info.value.message_dict


class TestProductCatalogUniqueness:

    def test_unique_name_per_tenant(self, client_account_a, user_a):
        from app_modules.product_catalog.models import ProductCatalog

        ProductCatalog(name='License').save(
            user=user_a, client_id=client_account_a.id
        )

        dup = ProductCatalog(name='License')
        with pytest.raises(IntegrityError):
            dup.save(user=user_a, client_id=client_account_a.id)

    def test_same_name_different_tenant(
        self, client_account_a, client_account_b, user_a, user_b
    ):
        from app_modules.product_catalog.models import ProductCatalog

        ProductCatalog(name='License').save(
            user=user_a, client_id=client_account_a.id
        )
        entry_b = ProductCatalog(name='License')
        entry_b.save(user=user_b, client_id=client_account_b.id)

        assert entry_b.pk is not None
