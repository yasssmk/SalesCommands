# backend/tests/bi/conftest.py
"""
Fixtures for BI-layer tests.

Re-exports the tenant / role fixtures from tests/signals/conftest.py (same
pattern as tests/permissions/conftest.py) so compute tests share the exact
production-shaped multi-tenant setup. Users / accounts / activities are built
locally per test.
"""

from tests.signals.conftest import (  # noqa: F401
    pytest_configure,
    tenant_a_id,
    tenant_b_id,
    client_account_a,
    client_account_b,
    role_individual_a,
    role_individual_b,
)
