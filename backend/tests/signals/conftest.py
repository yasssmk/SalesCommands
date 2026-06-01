# backend/tests/signals/conftest.py
"""
Pytest fixtures for the signals module tests.

Audit note: backend/tests/conftest.py does not exist at the time of
this sprint — there are no global fixtures to inherit. All fixtures
needed by the signals test pack are declared here. If/when a global
conftest is introduced, the user/role/tenant fixtures below should be
promoted up the tree and re-imported here without duplication.

Env vars : the project's settings.py reads SECRET_KEY, DATABASE_URL,
JWT_*_SECRET_KEY and OPENAI_API_KEY via `environ.Env`. These must be
set in the operator's environment (project convention: `.env` file at
the repo root, gitignored) BEFORE pytest is invoked — pytest-django
loads Django settings inside `pytest_load_initial_conftests`, which
runs before any conftest.py is imported, so we cannot inject defaults
from here.

Scope conventions:
  - All multi-tenant fixtures default to "tenant A" for the
    primary subject under test.
  - `other_tenant_*` fixtures provide a second isolated tenant
    used exclusively by cross-tenant tests in test_blocker_api.py.
  - Fixtures are minimal — only the fields required by BlockerSignal
    and its FK chain are populated.

Auth strategy:
  - `APIClient.force_authenticate(user=user, token=claims_dict)` is
    used to bypass real JWT verification. The claims_dict mirrors the
    shape produced by `core.jwt_helpers.CustomJWTAuthentication` so
    that `permissions.compat.get_auth_ctx` extracts the same fields.
  - JWT generation/validation is out of scope here — covered by
    dedicated auth tests elsewhere in the codebase.

Cache invalidation tests:
  - The `cache_invalidation_calls` fixture monkey-patches
    `app_modules.signals.signals.cache_invalidation.invalidate_tag`
    and records every call. Combined with
    `pytest.mark.django_db(transaction=True)`, this lets us assert
    that post-commit receivers fire with the expected (client_id,
    namespace) pairs.
"""

import uuid

import pytest
from rest_framework.test import APIClient


# =============================================================================
# DB DRIVER COMPAT — strip postgres-only OPTIONS when running on sqlite
# =============================================================================
# Production settings inject `OPTIONS = {"options": "-c statement_timeout=..."}`
# on the default database, which is a postgres-specific server-side parameter
# syntax. SQLite's Connection() rejects the `options=` keyword and explodes at
# connect time. When tests run against sqlite (sandbox / quick local runs),
# strip that key. The production (postgres) path is left untouched.

def pytest_configure(config):
    from django.conf import settings as dj_settings
    default_db = dj_settings.DATABASES.get('default', {})
    if (
        default_db.get('ENGINE', '').endswith('sqlite3')
        and 'OPTIONS' in default_db
        and 'options' in default_db['OPTIONS']
    ):
        # Drop the postgres server-side parameter string; keep the rest.
        default_db['OPTIONS'] = {
            k: v for k, v in default_db['OPTIONS'].items()
            if k != 'options'
        }


# =============================================================================
# SETTINGS PATCHES (autouse) — strip session auth + CSRF for API tests
# =============================================================================

@pytest.fixture(autouse=True)
def _jwt_only_no_csrf(settings):
    """
    Mirror of the pattern used in tests/integration/end_users/test_perm.py.

    1) DRF only validates via JWT (drops SessionAuthentication so we never
       trip CSRF on POST/PATCH/DELETE).
    2) Drops the Django CSRF middleware for the duration of the test.

    Both are necessary because APIClient.force_authenticate() bypasses
    auth backends but not the CSRF middleware on state-changing requests.
    """
    rf = dict(getattr(settings, 'REST_FRAMEWORK', {}))
    rf['DEFAULT_AUTHENTICATION_CLASSES'] = (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    )
    settings.REST_FRAMEWORK = rf

    settings.MIDDLEWARE = [
        m for m in settings.MIDDLEWARE
        if m != 'django.middleware.csrf.CsrfViewMiddleware'
    ]


# =============================================================================
# TENANT IDS — shared by user / account / activity / contact factories
# =============================================================================

@pytest.fixture
def tenant_a_id():
    """UUID for the primary tenant used by most tests."""
    return uuid.uuid4()


@pytest.fixture
def tenant_b_id():
    """UUID for a second isolated tenant — used by cross-tenant tests."""
    return uuid.uuid4()


# =============================================================================
# CLIENT ACCOUNTS — one per tenant
# =============================================================================

@pytest.fixture
def client_account_a(db, tenant_a_id):
    from end_users.models import ClientAccount
    return ClientAccount.objects.create(
        id=tenant_a_id,
        name='Tenant A Co',
        is_b2b=True,
        max_users=20,
    )


@pytest.fixture
def client_account_b(db, tenant_b_id):
    from end_users.models import ClientAccount
    return ClientAccount.objects.create(
        id=tenant_b_id,
        name='Tenant B Co',
        is_b2b=True,
        max_users=20,
    )


# =============================================================================
# ROLES — `individual` flag is sufficient for signals (registry matrix
# grants `client` scope on every CRUD action to individual / manager /
# admin alike). See permissions/registry/signals_registry.py.
# =============================================================================

@pytest.fixture
def role_individual_a(db, client_account_a):
    from end_users.models import UserRole
    return UserRole.objects.create(
        client_account=client_account_a,
        name='Individual',
        is_admin=False,
        is_manager=False,
        is_individual=True,
        read=True,
        write=True,
        modify=True,
        can_delete=True,
    )


@pytest.fixture
def role_individual_b(db, client_account_b):
    from end_users.models import UserRole
    return UserRole.objects.create(
        client_account=client_account_b,
        name='Individual',
        is_admin=False,
        is_manager=False,
        is_individual=True,
        read=True,
        write=True,
        modify=True,
        can_delete=True,
    )


# =============================================================================
# USERS — one acting rep per tenant
# =============================================================================

@pytest.fixture
def user_a(db, client_account_a, role_individual_a):
    from end_users.models import User
    return User.objects.create(
        email='rep-a@tenant-a.test',
        client_account=client_account_a,
        role=role_individual_a,
        is_active=True,
    )


@pytest.fixture
def user_b(db, client_account_b, role_individual_b):
    from end_users.models import User
    return User.objects.create(
        email='rep-b@tenant-b.test',
        client_account=client_account_b,
        role=role_individual_b,
        is_active=True,
    )


# =============================================================================
# COMPANY ACCOUNTS (the customer being tracked) — scoped to a tenant
# =============================================================================

@pytest.fixture
def account(db, client_account_a, user_a):
    from app_modules.accounts.models import CompanyAccount
    acc = CompanyAccount(
        company_name='Acme Corp',
        has_buying_decision=True,
    )
    acc.save(user=user_a, client_id=client_account_a.id)
    return acc


@pytest.fixture
def other_tenant_account(db, client_account_b, user_b):
    from app_modules.accounts.models import CompanyAccount
    acc = CompanyAccount(
        company_name='Globex Inc',
        has_buying_decision=True,
    )
    acc.save(user=user_b, client_id=client_account_b.id)
    return acc


# =============================================================================
# ACTIVITIES — a call/meeting from which signals are extracted
# =============================================================================

@pytest.fixture
def activity(db, account, user_a):
    from app_modules.activities.models import Activity
    from app_modules.activities.constants import ActivityType, ActivityStatus
    a = Activity(
        title='Discovery call with Acme',
        activity_type=ActivityType.MEETING,
        status=ActivityStatus.COMPLETED,
        account=account,
        owner=user_a,
    )
    a.save(user=user_a, client_id=account.client_id)
    return a


@pytest.fixture
def other_tenant_activity(db, other_tenant_account, user_b):
    from app_modules.activities.models import Activity
    from app_modules.activities.constants import ActivityType, ActivityStatus
    a = Activity(
        title='Discovery call with Globex',
        activity_type=ActivityType.MEETING,
        status=ActivityStatus.COMPLETED,
        account=other_tenant_account,
        owner=user_b,
    )
    a.save(user=user_b, client_id=other_tenant_account.client_id)
    return a


# =============================================================================
# CONTACT — used both as blocker attribution and for SET_NULL semantics
# =============================================================================

@pytest.fixture
def contact(db, account, user_a):
    from app_modules.contacts.models import Contact
    c = Contact(
        account=account,
        first_name='Jane',
        last_name='Doe',
        job_title='VP Engineering',
    )
    c.save(user=user_a, client_id=account.client_id)
    return c


# =============================================================================
# API CLIENT
# =============================================================================

@pytest.fixture
def api():
    """Bare DRF APIClient — no CSRF enforcement."""
    return APIClient(enforce_csrf_checks=False)


# =============================================================================
# AUTH HELPER — returns a callable that authenticates a given client
# =============================================================================

@pytest.fixture
def authenticate():
    """
    Returns a helper(client, user, tenant_id) that mounts both the
    DRF force_authenticate token and the tenant headers used by the
    custom middleware. Mirrors the production payload shape produced
    by `core.jwt_helpers.CustomJWTAuthentication` so that
    `permissions.compat.get_auth_ctx` extracts identical fields.
    """
    def _do(api_client, user, tenant_id):
        role = user.role
        claims = {
            'origin': 'end_users',
            'user_id': str(user.id),
            'client_account': str(tenant_id),
            'role': {
                'id': str(role.id) if role else '',
                'name': role.name if role else '',
                'is_admin': bool(getattr(role, 'is_admin', False)) if role else False,
                'is_manager': bool(getattr(role, 'is_manager', False)) if role else False,
                'is_individual': bool(getattr(role, 'is_individual', False)) if role else False,
            },
            'is_superuser': bool(user.is_superuser),
        }
        api_client.force_authenticate(user=user, token=claims)
        api_client.credentials(
            HTTP_X_CLIENT_ID=str(tenant_id),
            HTTP_CLIENT_ID=str(tenant_id),
            HTTP_X_TENANT_ID=str(tenant_id),
            HTTP_AUTHORIZATION='Bearer test-token',
        )
    return _do


@pytest.fixture
def authed_api_a(api, authenticate, user_a, client_account_a):
    """APIClient authenticated as user_a on tenant A."""
    authenticate(api, user_a, client_account_a.id)
    return api


@pytest.fixture
def authed_api_b(api, authenticate, user_b, client_account_b):
    """APIClient authenticated as user_b on tenant B — for cross-tenant tests."""
    authenticate(api, user_b, client_account_b.id)
    return api


# =============================================================================
# CACHE INVALIDATION SPY
# =============================================================================

@pytest.fixture
def cache_invalidation_calls(monkeypatch):
    """
    Record every call to `invalidate_tag` originating from the signals
    module's post_save / post_delete receivers.

    Returns the list of `(client_id, namespace)` tuples captured. Used
    by test_blocker_model.py to assert that BlockerSignal writes bust
    SIGNALS_CACHE_TAG and do NOT bust SIGNAL_CLUSTERS_CACHE_TAG.
    """
    from app_modules.signals.signals import cache_invalidation

    calls = []

    def _spy(client_id, namespace):
        calls.append((str(client_id), namespace))
        return 1  # mimic the production return shape

    monkeypatch.setattr(cache_invalidation, 'invalidate_tag', _spy)
    return calls
