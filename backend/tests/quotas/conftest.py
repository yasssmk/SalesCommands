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
    client_account_a,
    role_individual_a,
    user_a,
    api,
    authenticate,
    authed_api_a,
)
