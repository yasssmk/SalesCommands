# backend/tests/activities/conftest.py
"""
Pytest fixtures for the activities module tests.

Re-exports the tenant / role / user / account / api / auth fixtures from
tests/signals/conftest.py (same pattern as tests/decision_cycles/conftest.py),
so activity permission tests share the exact production-shaped JWT auth and
multi-tenant setup.
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
    account,
    other_tenant_account,
    other_tenant_activity,
    api,
    authenticate,
    authed_api_a,
    authed_api_b,
)
