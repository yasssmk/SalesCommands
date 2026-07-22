# backend/tests/territories/conftest.py
"""
Fixtures for territory-count tests.

Re-exports the production-shaped tenant / role / auth fixtures from
tests/signals/conftest.py (same pattern as tests/bi/conftest.py), so the
counts endpoint is exercised through the real multi-tenant auth path. Users,
accounts and contacts are built locally per test.
"""

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
    api,
    authenticate,
    authed_api_a,
    authed_api_b,
)
