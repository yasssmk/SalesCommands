# backend/tests/permissions/test_scope_filter.py
"""
Unit tests for the shared role-scope callable (permissions/scope_filter.py).

This is the anti-divergence guardrail extracted from ScopedQuerysetMixin so
that view and non-view (BI) consumers apply IDENTICAL scope filtering.

The critical guarantee, proven here at the callable level: `mine` scope
INCLUDES records whose parent account is owned by the user
(C6 account-owner inheritance, account__account_owner_id) — even when the
record itself was created/owned by someone else.

We also pin the contract for `client` / `none` scopes, the negative case
(a non-owner sees nothing of another rep's account), and DOCUMENT that the
older permissions.scoping.apply_scope_filter path does NOT carry C6 — which
is exactly why BI must reuse apply_role_scope, not that path.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.activities.models import Activity
from app_modules.accounts.models import CompanyAccount
from permissions.compat import AuthContext
from permissions.scope_filter import apply_role_scope


# =============================================================================
# FIXTURES — AE (account owner), SDR (creator of the activity), unrelated rep
# =============================================================================

@pytest.fixture
def ae_user(db, client_account_a, role_individual_a):
    """Account Executive — owns the account under test."""
    from end_users.models import User
    return User.objects.create(
        email='ae-scope@tenant-a.test',
        client_account=client_account_a,
        role=role_individual_a,
        is_active=True,
    )


@pytest.fixture
def sdr_user(db, client_account_a, role_individual_a):
    """SDR — creates/owns the activity but does not own the account."""
    from end_users.models import User
    return User.objects.create(
        email='sdr-scope@tenant-a.test',
        client_account=client_account_a,
        role=role_individual_a,
        is_active=True,
    )


@pytest.fixture
def other_user(db, client_account_a, role_individual_a):
    """Unrelated rep on the same tenant, owns nothing under test."""
    from end_users.models import User
    return User.objects.create(
        email='other-scope@tenant-a.test',
        client_account=client_account_a,
        role=role_individual_a,
        is_active=True,
    )


@pytest.fixture
def account_ae(db, client_account_a, ae_user):
    """CompanyAccount whose account_owner is the AE."""
    acc = CompanyAccount(
        company_name='AE Owned Corp (scope)',
        has_buying_decision=True,
        account_owner=ae_user,
    )
    acc.save(user=ae_user, client_id=client_account_a.id)
    return acc


@pytest.fixture
def sdr_activity(db, account_ae, sdr_user, client_account_a):
    """Activity on the AE-owned account, created and owned by the SDR."""
    a = Activity(
        title='SDR prospecting call (scope)',
        activity_type=ActivityType.MEETING,
        status=ActivityStatus.PLANNED,
        account=account_ae,
        owner=sdr_user,
        scheduled_date=timezone.now().date() + timedelta(days=5),
    )
    a.save(user=sdr_user, client_id=client_account_a.id)
    return a


def _ctx(user, client_account):
    """Build a minimal AuthContext like get_auth_ctx would from a JWT."""
    return AuthContext(
        user_id=str(user.id),
        client_id=str(client_account.id),
        is_authenticated=True,
    )


def _base_qs(client_account):
    """Tenant-filtered base queryset (as the mixin passes to apply_role_scope)."""
    return Activity.objects.filter(client_id=client_account.id)


# =============================================================================
# POSITIVE — mine scope carries C6 account-owner inheritance
# =============================================================================

@pytest.mark.django_db
class TestMineScopeC6:

    def test_mine_includes_account_owned_activity(
        self, ae_user, client_account_a, account_ae, sdr_activity
    ):
        """The AE owns the account; under `mine` they must see the
        SDR-created activity on that account (account__account_owner_id)."""
        qs = apply_role_scope(
            _base_qs(client_account_a),
            module='activities',
            scope='mine',
            auth_ctx=_ctx(ae_user, client_account_a),
        )
        assert sdr_activity.id in set(qs.values_list('id', flat=True))

    def test_mine_owner_also_sees_own_activity(
        self, sdr_user, client_account_a, account_ae, sdr_activity
    ):
        """Sanity: the direct owner (SDR) still sees their own activity."""
        qs = apply_role_scope(
            _base_qs(client_account_a),
            module='activities',
            scope='mine',
            auth_ctx=_ctx(sdr_user, client_account_a),
        )
        assert sdr_activity.id in set(qs.values_list('id', flat=True))


# =============================================================================
# NEGATIVE — a rep who owns neither the account nor the activity sees nothing
# =============================================================================

@pytest.mark.django_db
class TestMineScopeNegative:

    def test_mine_excludes_unrelated_rep(
        self, other_user, client_account_a, account_ae, sdr_activity
    ):
        """other_user is neither owner, creator, nor account owner -> excluded."""
        qs = apply_role_scope(
            _base_qs(client_account_a),
            module='activities',
            scope='mine',
            auth_ctx=_ctx(other_user, client_account_a),
        )
        assert sdr_activity.id not in set(qs.values_list('id', flat=True))


# =============================================================================
# CONTRACT — client / none scope behaviour
# =============================================================================

@pytest.mark.django_db
class TestScopeContract:

    def test_client_scope_returns_unchanged(
        self, other_user, client_account_a, account_ae, sdr_activity
    ):
        """client scope = already tenant-filtered by caller -> unchanged."""
        base = _base_qs(client_account_a)
        qs = apply_role_scope(
            base, module='activities', scope='client',
            auth_ctx=_ctx(other_user, client_account_a),
        )
        assert sdr_activity.id in set(qs.values_list('id', flat=True))
        assert qs.count() == base.count()

    def test_none_scope_is_empty(
        self, ae_user, client_account_a, account_ae, sdr_activity
    ):
        for scope in (None, 'none'):
            qs = apply_role_scope(
                _base_qs(client_account_a), module='activities', scope=scope,
                auth_ctx=_ctx(ae_user, client_account_a),
            )
            assert qs.count() == 0


# =============================================================================
# GUARDRAIL — the older scoping.apply_scope_filter path LACKS C6
# (documents exactly why BI must reuse apply_role_scope, not that path)
# =============================================================================

@pytest.mark.django_db
class TestDivergenceGuardrail:

    def test_scoping_apply_scope_filter_drops_c6(
        self, ae_user, client_account_a, account_ae, sdr_activity
    ):
        """permissions.scoping.apply_scope_filter has no account_owner term, so
        under `mine` the AE does NOT see the account-owned activity. This is the
        divergence apply_role_scope exists to prevent — asserted so any future
        change that accidentally makes them equivalent is caught."""
        from permissions.scoping import apply_scope_filter

        qs = apply_scope_filter(
            _base_qs(client_account_a), 'activities', 'mine', ae_user,
        )
        assert sdr_activity.id not in set(qs.values_list('id', flat=True))

        # ...whereas the shared callable DOES include it (same inputs).
        qs_shared = apply_role_scope(
            _base_qs(client_account_a),
            module='activities', scope='mine',
            auth_ctx=_ctx(ae_user, client_account_a),
        )
        assert sdr_activity.id in set(qs_shared.values_list('id', flat=True))
