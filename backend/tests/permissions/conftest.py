# backend/tests/permissions/conftest.py
"""
Fixtures for permissions-layer tests.

Re-exports the tenant / role fixtures from tests/signals/conftest.py (same
pattern as tests/activities/conftest.py) so scope-filter tests share the
exact production-shaped multi-tenant setup. Users/accounts are built locally
per test.
"""

from tests.signals.conftest import (  # noqa: F401
    pytest_configure,
    tenant_a_id,
    client_account_a,
    role_individual_a,
)
