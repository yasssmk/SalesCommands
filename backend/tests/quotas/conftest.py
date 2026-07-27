# backend/tests/quotas/conftest.py
"""
Fixtures for the quotas module tests.

Re-exports the tenant / user / role fixtures from tests/signals/conftest.py
(same pattern as tests/decision_cycles/conftest.py).
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
)
