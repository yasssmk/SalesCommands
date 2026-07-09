# backend/tests/notifications/conftest.py
"""
Pytest fixtures for the notifications module tests.

Re-exports the tenant / role / user fixtures from
backend/tests/signals/conftest.py (same pattern as
tests/decision_cycles/conftest.py) and adds a second recipient on
tenant A so recipient-level isolation can be exercised independently
of tenant-level isolation.

Re-exported from tests/signals/conftest.py:
    pytest_configure, _jwt_only_no_csrf,
    tenant_a_id, tenant_b_id, client_account_a, client_account_b,
    role_individual_a, role_individual_b, user_a, user_b,
    account, api, authenticate, authed_api_a, authed_api_b

New fixtures (notifications-specific):
    user_a2   -- a second active user on tenant A (distinct recipient)
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


# =============================================================================
# SECOND RECIPIENT ON TENANT A — distinct user, same tenant
# =============================================================================

@pytest.fixture
def user_a2(db, client_account_a, role_individual_a):
    """A second active user on tenant A, used as a distinct recipient."""
    from end_users.models import User
    return User.objects.create(
        email='rep-a2@tenant-a.test',
        client_account=client_account_a,
        role=role_individual_a,
        is_active=True,
    )
