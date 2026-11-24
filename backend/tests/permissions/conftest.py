# backend/tests/permissions/conftest.py
"""
Fixtures for permissions-layer tests.

Re-exports the tenant / role fixtures from tests/signals/conftest.py (same
pattern as tests/activities/conftest.py) so scope-filter tests share the
exact production-shaped multi-tenant setup. Users/accounts are built locally
per test.

Also hosts the single shared walker of the live URL configuration
(``live_view_classes``), used by the tenant-filter guardrails.
"""

import pytest
from django.urls import URLPattern, URLResolver, get_resolver

from tests.signals.conftest import (  # noqa: F401
    pytest_configure,
    tenant_a_id,
    client_account_a,
    role_individual_a,
)


@pytest.fixture(scope='session')
def live_view_classes():
    """Every view class reachable through the project's URL configuration
    (ROOT_URLCONF, nested includes included). ViewSets and class-based views
    expose their class as ``callback.cls`` / ``callback.view_class``."""
    def walk(patterns):
        for p in patterns:
            if isinstance(p, URLResolver):
                yield from walk(p.url_patterns)
            elif isinstance(p, URLPattern):
                cls = getattr(p.callback, 'cls', None) or getattr(p.callback, 'view_class', None)
                if cls is not None:
                    yield cls
    return frozenset(walk(get_resolver().url_patterns))
