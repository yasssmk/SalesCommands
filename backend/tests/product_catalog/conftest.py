# backend/tests/product_catalog/conftest.py
"""
Pytest fixtures for the ProductCatalog module tests.

Re-exports tenant / user / auth fixtures from tests/signals/conftest.py
and adds product-catalog-specific fixtures.
"""

import pytest

from tests.signals.conftest import (  # noqa: F401
    pytest_configure,
    _jwt_only_no_csrf,
    tenant_a_id,
    tenant_b_id,
    client_account_a,
    client_account_b,
    role_individual_a,
    role_individual_b,
    user_a,
    user_b,
    account,
    api,
    authenticate,
    authed_api_a,
    authed_api_b,
)


@pytest.fixture
def product_entry(db, client_account_a, user_a):
    """A single ProductCatalog entry on tenant A."""
    from app_modules.product_catalog.models import ProductCatalog

    entry = ProductCatalog(
        name='Enterprise License',
        description='Annual subscription',
        default_unit_price=10000,
    )
    entry.save(user=user_a, client_id=client_account_a.id)
    return entry
