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


@pytest.fixture
def role_admin_a(db, client_account_a):
    """
    Retrieve the 'Admin' role bootstrapped by the ClientAccount signal.
    """
    from end_users.models import UserRole

    return UserRole.objects.get(
        client_account=client_account_a,
        name='Admin',
    )


@pytest.fixture
def admin_user_a(db, client_account_a, role_admin_a):
    """Admin user on tenant A for write-path tests."""
    from end_users.models import User

    return User.objects.create(
        email='admin@tenant-a.test',
        client_account=client_account_a,
        role=role_admin_a,
        is_active=True,
    )


@pytest.fixture
def authed_admin_api_a(api, authenticate, admin_user_a, client_account_a):
    """APIClient authenticated as admin on tenant A."""
    authenticate(api, admin_user_a, client_account_a.id)
    return api
