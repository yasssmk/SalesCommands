# backend/tests/quotas/test_quota_model_and_permissions.py
"""
Quota (personal Sales objective) — model, derived state, and registry-scoped
permissions.

Covers:
- derived state (past / current / future) — no stored flag;
- overlap allowed (concurrent overlapping objectives coexist);
- source_campaign nullable (global + campaign-scoped coexist, campaign filter
  does not drop global objectives);
- CRUD scoping via the existing primitives (apply_role_scope + OWNERSHIP_MAP):
  individual sees only their own, manager reads the team but cannot edit a
  member's, admin reads all — positive AND negative;
- config.MODULES registration: the effective scope comes from the registry,
  NOT the fail-open 'client'.

DB: Postgres.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app_modules.bi.metrics import MetricKey
from app_modules.quotas.models import Quota, QuotaState
from permissions.checks import check_permission
from permissions.config import is_module_enabled
from permissions.registry import get_scope
from permissions.scope_filter import apply_role_scope
from permissions.compat import AuthContext


TODAY = date.today()


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _ctx(user, ca):
    return AuthContext(user_id=str(user.id), client_id=str(ca.id), is_authenticated=True)


def _mk_user(email, ca, role):
    from end_users.models import User
    return User.objects.create(email=email, client_account=ca, role=role, is_active=True)


def _mk_role(ca, name, *, admin=False, manager=False, individual=False):
    from end_users.models import UserRole
    return UserRole.objects.create(
        client_account=ca, name=name, is_admin=admin, is_manager=manager,
        is_individual=individual, read=True, write=True, modify=True, can_delete=True,
    )


def _mk_campaign(owner, ca):
    from app_modules.campaigns.models.campaign import Campaign
    c = Campaign(name='Camp', campaign_type='OUTBOUND', owner=owner, executor=owner,
                 planned_start_date=TODAY, planned_end_date=TODAY + timedelta(days=30))
    c.save(user=owner, client_id=ca.id)
    return c


def _mk_quota(owner, ca, *, metric=MetricKey.MEETINGS, target=Decimal('10'),
              start=None, end=None, source_campaign=None):
    q = Quota(
        owner=owner, metric=metric, target_value=target,
        period_start=start or TODAY - timedelta(days=5),
        period_end=end or TODAY + timedelta(days=5),
        source_campaign=source_campaign,
    )
    q.save(user=owner, client_id=ca.id)
    return q


def _qs(ca):
    return Quota.objects.filter(client_id=ca.id)


# ---------------------------------------------------------------------------
# Derived state — no stored flag
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDerivedState:

    def test_current_when_window_covers_today(self, user_a, client_account_a):
        q = _mk_quota(user_a, client_account_a,
                      start=TODAY - timedelta(days=1), end=TODAY + timedelta(days=1))
        assert q.get_state() == QuotaState.CURRENT
        assert q.is_current is True

    def test_past_when_ended_before_today(self, user_a, client_account_a):
        q = _mk_quota(user_a, client_account_a,
                      start=TODAY - timedelta(days=30), end=TODAY - timedelta(days=1))
        assert q.get_state() == QuotaState.PAST
        assert q.is_current is False

    def test_future_when_starts_after_today(self, user_a, client_account_a):
        q = _mk_quota(user_a, client_account_a,
                      start=TODAY + timedelta(days=1), end=TODAY + timedelta(days=30))
        assert q.get_state() == QuotaState.FUTURE
        assert q.is_current is False

    def test_boundaries_are_inclusive(self, user_a, client_account_a):
        # window is exactly [today, today]
        q = _mk_quota(user_a, client_account_a, start=TODAY, end=TODAY)
        assert q.get_state() == QuotaState.CURRENT

    def test_state_is_not_a_stored_field(self):
        field_names = {f.name for f in Quota._meta.get_fields()}
        assert 'is_current' not in field_names
        assert 'state' not in field_names


# ---------------------------------------------------------------------------
# Overlap allowed
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestOverlapAllowed:

    def test_two_overlapping_quotas_coexist(self, user_a, client_account_a):
        _mk_quota(user_a, client_account_a,
                  start=TODAY - timedelta(days=10), end=TODAY + timedelta(days=10))
        # fully overlapping window, same user, same metric — must NOT raise
        _mk_quota(user_a, client_account_a,
                  start=TODAY - timedelta(days=5), end=TODAY + timedelta(days=20))
        assert _qs(client_account_a).filter(owner=user_a).count() == 2


# ---------------------------------------------------------------------------
# source_campaign nullable
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestSourceCampaignNullable:

    def test_global_and_campaign_scoped_coexist(self, user_a, client_account_a):
        camp = _mk_campaign(user_a, client_account_a)
        glob = _mk_quota(user_a, client_account_a, source_campaign=None)
        scoped = _mk_quota(user_a, client_account_a, source_campaign=camp)
        assert glob.source_campaign_id is None
        assert scoped.source_campaign_id == camp.id
        assert _qs(client_account_a).count() == 2

    def test_campaign_filter_keeps_globals_out_but_does_not_delete_them(
            self, user_a, client_account_a):
        camp = _mk_campaign(user_a, client_account_a)
        _mk_quota(user_a, client_account_a, source_campaign=None)      # global
        _mk_quota(user_a, client_account_a, source_campaign=camp)       # declined
        # filtering by campaign returns only the declined one...
        assert _qs(client_account_a).filter(source_campaign=camp).count() == 1
        # ...but the global one still exists (the "current" stays global).
        assert _qs(client_account_a).filter(source_campaign__isnull=True).count() == 1


# ---------------------------------------------------------------------------
# CRUD scoping (apply_role_scope + OWNERSHIP_MAP['quotas'])
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestScoping:

    def test_individual_sees_only_own(self, client_account_a, role_individual_a):
        a = _mk_user('a@a.test', client_account_a, role_individual_a)
        b = _mk_user('b@a.test', client_account_a, role_individual_a)
        qa = _mk_quota(a, client_account_a)
        qb = _mk_quota(b, client_account_a)
        scoped = apply_role_scope(_qs(client_account_a), module='quotas',
                                  scope='mine', auth_ctx=_ctx(a, client_account_a))
        ids = set(scoped.values_list('id', flat=True))
        assert qa.id in ids          # own
        assert qb.id not in ids      # NOT another user's (negative)
        assert scoped.count() == 1

    def test_manager_reads_team_but_not_outsider(self, client_account_a, role_individual_a):
        from end_users.models import Team
        manager = _mk_user('mgr@a.test', client_account_a, role_individual_a)
        team = Team.objects.create(name='T', client_account=client_account_a, manager=manager)
        member = _mk_user('mem@a.test', client_account_a, role_individual_a)
        member.team = team
        member.save()
        outsider = _mk_user('out@a.test', client_account_a, role_individual_a)

        q_member = _mk_quota(member, client_account_a)
        q_outsider = _mk_quota(outsider, client_account_a)

        scoped = apply_role_scope(_qs(client_account_a), module='quotas',
                                  scope='team', auth_ctx=_ctx(manager, client_account_a))
        ids = set(scoped.values_list('id', flat=True))
        assert q_member.id in ids        # team member's objective (positive)
        assert q_outsider.id not in ids  # unrelated user's (negative)

    def test_manager_cannot_edit_member_quota_scope_is_mine(
            self, client_account_a, role_individual_a):
        # update scope for a manager is 'mine' -> editing a member's quota is
        # out of the manager's editable set.
        from end_users.models import Team
        manager = _mk_user('mgr2@a.test', client_account_a, role_individual_a)
        team = Team.objects.create(name='T2', client_account=client_account_a, manager=manager)
        member = _mk_user('mem2@a.test', client_account_a, role_individual_a)
        member.team = team
        member.save()
        q_member = _mk_quota(member, client_account_a)

        assert get_scope('quotas', 'update', 'manager') == 'mine'
        editable = apply_role_scope(_qs(client_account_a), module='quotas',
                                    scope='mine', auth_ctx=_ctx(manager, client_account_a))
        assert q_member.id not in set(editable.values_list('id', flat=True))

    def test_admin_reads_all(self, client_account_a, role_individual_a):
        a = _mk_user('a2@a.test', client_account_a, role_individual_a)
        b = _mk_user('b2@a.test', client_account_a, role_individual_a)
        _mk_quota(a, client_account_a)
        _mk_quota(b, client_account_a)
        admin = _mk_user('admin@a.test', client_account_a, role_individual_a)
        scoped = apply_role_scope(_qs(client_account_a), module='quotas',
                                  scope='client', auth_ctx=_ctx(admin, client_account_a))
        assert scoped.count() == 2   # client scope returns the whole tenant


# ---------------------------------------------------------------------------
# Registry matrix + config.MODULES registration (NOT fail-open)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestRegistryAndModuleRegistration:

    def test_registry_matrix(self):
        # create/update/delete = mine for every tier (each manages their own)
        for action in ('create', 'update', 'delete'):
            for tier in ('individual', 'manager', 'admin'):
                assert get_scope('quotas', action, tier) == 'mine', (action, tier)
        # read widens with the tier
        assert get_scope('quotas', 'read', 'individual') == 'mine'
        assert get_scope('quotas', 'read', 'manager') == 'team'
        assert get_scope('quotas', 'read', 'admin') == 'client'

    def test_module_registered_in_config(self):
        assert is_module_enabled('quotas') is True

    def test_effective_scope_comes_from_registry_not_failopen(
            self, client_account_a):
        # An individual's read must resolve to 'mine' via the registry. Were the
        # module absent from config.MODULES, checks.py would fail OPEN to
        # 'client' — so 'mine' proves the registry (not the fail-open) decided.
        role = _mk_role(client_account_a, 'Ind', individual=True)
        user = _mk_user('ind@a.test', client_account_a, role)
        scope = check_permission(user, 'quotas', 'read')
        assert scope == 'mine'
        assert scope != 'client'
