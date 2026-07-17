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
from app_modules.territories.models import Territory
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
# POSITIVE — team scope carries the SAME C6 (a NON-member's activity on a
# MEMBER's account), bounded to team members so the boundary holds.
# =============================================================================

@pytest.mark.django_db
class TestTeamScopeC6:

    def _manager_of(self, ae_user, client_account_a):
        """Make a manager whose team the AE belongs to. Returns the manager."""
        from end_users.models import Team, User
        mgr = User.objects.create(email='mgr-scope@tenant-a.test',
                                  client_account=client_account_a,
                                  role=ae_user.role, is_active=True)
        team = Team.objects.create(name='EMEA (scope)', client_account=client_account_a,
                                   manager=mgr)
        ae_user.team = team
        ae_user.save(update_fields=['team'])
        return mgr

    def test_team_includes_non_member_activity_on_a_member_account(
        self, ae_user, sdr_user, client_account_a, account_ae, sdr_activity
    ):
        """The AE is a team member; the SDR (NOT a member) posted an activity on
        the AE's account. Under `team` the manager must see it (C6) — the exact
        pendant of mine's C6, one level up. This is the manager DC-block / todo
        fix at the primitive level."""
        mgr = self._manager_of(ae_user, client_account_a)
        qs = apply_role_scope(
            _base_qs(client_account_a),
            module='activities',
            scope='team',
            auth_ctx=_ctx(mgr, client_account_a),
        )
        assert sdr_activity.id in set(qs.values_list('id', flat=True))

    def test_team_boundary_excludes_activity_on_out_of_hierarchy_account(
        self, ae_user, sdr_user, other_user, client_account_a, account_ae, sdr_activity
    ):
        """C6 is bounded to team members as the account owner: an activity on an
        account owned OUTSIDE the manager's hierarchy never enters team scope."""
        mgr = self._manager_of(ae_user, client_account_a)
        # other_user is NOT in the manager's team; an account they own, worked by
        # the SDR -> must stay out of the manager's team scope.
        out_acc = CompanyAccount(company_name='Outsider Corp (scope)',
                                 has_buying_decision=True, account_owner=other_user)
        out_acc.save(user=other_user, client_id=client_account_a.id)
        out_act = Activity(title='SDR call on outsider account',
                           activity_type=ActivityType.MEETING, status=ActivityStatus.PLANNED,
                           account=out_acc, owner=sdr_user,
                           scheduled_date=timezone.now().date() + timedelta(days=5))
        out_act.save(user=sdr_user, client_id=client_account_a.id)

        qs = apply_role_scope(
            _base_qs(client_account_a),
            module='activities',
            scope='team',
            auth_ctx=_ctx(mgr, client_account_a),
        )
        ids = set(qs.values_list('id', flat=True))
        assert sdr_activity.id in ids       # on a member's account -> in
        assert out_act.id not in ids        # on an outsider's account -> out (boundary)


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


# =============================================================================
# TERRITORY OWNER SCOPE — the guardrail for the OWNERSHIP_MAP['territories'] fix
# (owner_user='owner' / created_by='created_by', bare names). This locks the
# behaviour independently of KPI 4, the same way the C6 tests above lock
# account-owner inheritance: if the map ever regresses to the '_id' attnames,
# _is_valid_field rejects them and mine/team silently returns none() — caught
# here.
# =============================================================================

@pytest.fixture
def owner_a(db, client_account_a, role_individual_a):
    from end_users.models import User
    return User.objects.create(
        email='terr-owner-a@tenant-a.test', client_account=client_account_a,
        role=role_individual_a, is_active=True,
    )


@pytest.fixture
def owner_b(db, client_account_a, role_individual_a):
    from end_users.models import User
    return User.objects.create(
        email='terr-owner-b@tenant-a.test', client_account=client_account_a,
        role=role_individual_a, is_active=True,
    )


def _mk_territory(owner, client_account, name):
    t = Territory(name=name, type='ACCOUNT', owner=owner, filter_definition={})
    t.save(user=owner, client_id=client_account.id)
    return t


def _terr_qs(client_account):
    return Territory.objects.filter(client_id=client_account.id)


@pytest.mark.django_db
class TestTerritoryOwnerScope:

    def test_mine_includes_own_territory(self, owner_a, client_account_a):
        t_a = _mk_territory(owner_a, client_account_a, 'Terr A')
        qs = apply_role_scope(
            _terr_qs(client_account_a), module='territories', scope='mine',
            auth_ctx=_ctx(owner_a, client_account_a),
        )
        assert t_a.id in set(qs.values_list('id', flat=True))

    def test_mine_excludes_other_owners_territory(self, owner_a, owner_b, client_account_a):
        t_a = _mk_territory(owner_a, client_account_a, 'Terr A')
        t_b = _mk_territory(owner_b, client_account_a, 'Terr B')
        qs = apply_role_scope(
            _terr_qs(client_account_a), module='territories', scope='mine',
            auth_ctx=_ctx(owner_a, client_account_a),
        )
        ids = set(qs.values_list('id', flat=True))
        assert t_a.id in ids          # owner sees their own
        assert t_b.id not in ids      # NOT another owner's

    def test_mine_is_not_empty_regression_guard(self, owner_a, owner_b, client_account_a):
        """If OWNERSHIP_MAP['territories'] regressed to '_id' attnames, mine
        would resolve no valid ownership field and return none(). Assert the
        owner actually gets a non-empty scoped queryset."""
        _mk_territory(owner_a, client_account_a, 'Terr A')
        _mk_territory(owner_b, client_account_a, 'Terr B')
        qs = apply_role_scope(
            _terr_qs(client_account_a), module='territories', scope='mine',
            auth_ctx=_ctx(owner_a, client_account_a),
        )
        assert qs.count() == 1  # exactly the owner's one — not 0 (none-bug), not 2 (all)

    def test_client_scope_sees_all_territories(self, owner_a, owner_b, client_account_a):
        _mk_territory(owner_a, client_account_a, 'Terr A')
        _mk_territory(owner_b, client_account_a, 'Terr B')
        qs = apply_role_scope(
            _terr_qs(client_account_a), module='territories', scope='client',
            auth_ctx=_ctx(owner_a, client_account_a),
        )
        assert qs.count() == 2  # client scope = whole tenant, no owner filter


# =============================================================================
# SALES-QUOTA OWNER SCOPE — guardrail for the OWNERSHIP_MAP['sales_quotas'] fix
# (owner_user='user', owner_team='user__team_id', created_by='created_by').
# A quota is PERSONAL, sensitive data: a user must not see another user's
# quota (mine), and a manager sees their team's (team). Third symptom of the
# same attname bug (after territories) — locked here independently of KPI 8.
# =============================================================================

def _mk_quota(user, client_account):
    from datetime import date
    from end_users.models import SalesQuota
    q = SalesQuota(
        user=user, name=f'Q-{user.email}', target_type='meetings',
        target_value=10, recurrence_type='annual', fiscal_year=2026,
        period_number=1, period_start=date(2026, 1, 1), period_end=date(2026, 12, 31),
    )
    q.save()  # client_id auto-set from user
    return q


def _quota_qs(client_account):
    from end_users.models import SalesQuota
    return SalesQuota.objects.filter(client_id=client_account.id)


@pytest.fixture
def q_user_a(db, client_account_a, role_individual_a):
    from end_users.models import User
    return User.objects.create(email='q-a@tenant-a.test', client_account=client_account_a,
                               role=role_individual_a, is_active=True)


@pytest.fixture
def q_user_b(db, client_account_a, role_individual_a):
    from end_users.models import User
    return User.objects.create(email='q-b@tenant-a.test', client_account=client_account_a,
                               role=role_individual_a, is_active=True)


@pytest.mark.django_db
class TestSalesQuotaOwnerScope:

    def test_mine_sees_own_quota_not_others(self, q_user_a, q_user_b, client_account_a):
        qa = _mk_quota(q_user_a, client_account_a)
        qb = _mk_quota(q_user_b, client_account_a)
        scoped = apply_role_scope(
            _quota_qs(client_account_a), module='sales_quotas', scope='mine',
            auth_ctx=_ctx(q_user_a, client_account_a),
        )
        ids = set(scoped.values_list('id', flat=True))
        assert qa.id in ids          # own quota
        assert qb.id not in ids      # NOT another user's (personal data)
        assert scoped.count() == 1   # non-empty regression guard (not 0=none-bug, not 2=all)

    def test_manager_team_scope_sees_members_quota(self, client_account_a, role_individual_a):
        from end_users.models import User, Team

        manager = User.objects.create(email='mgr@tenant-a.test', client_account=client_account_a,
                                      role=role_individual_a, is_active=True)
        team = Team.objects.create(name='Team X', client_account=client_account_a, manager=manager)
        member = User.objects.create(email='member@tenant-a.test', client_account=client_account_a,
                                     role=role_individual_a, is_active=True, team=team)
        outsider = User.objects.create(email='out@tenant-a.test', client_account=client_account_a,
                                       role=role_individual_a, is_active=True)

        q_member = _mk_quota(member, client_account_a)
        q_outsider = _mk_quota(outsider, client_account_a)

        scoped = apply_role_scope(
            _quota_qs(client_account_a), module='sales_quotas', scope='team',
            auth_ctx=_ctx(manager, client_account_a),
        )
        ids = set(scoped.values_list('id', flat=True))
        assert q_member.id in ids        # manager sees their team member's quota
        assert q_outsider.id not in ids  # NOT an unrelated user's quota


# =============================================================================
# ACCOUNT OWNER SCOPE — guardrail for the OWNERSHIP_MAP['accounts'] fix
# (owner_user='account_owner', owner_team='account_owner__team_id'). CompanyAccount
# is the MOST CENTRAL model: `account_owner_id` was the attname (rejected by
# _is_valid_field) → mine returned none() (created_by/assigned are '-', so it
# was the ONLY mine term). Same attname bug as territories/sales_quotas, locked
# here independently. NOTE: this is distinct from the C6 tests above — those
# assert account__account_owner_id traversal on OTHER modules (activities); this
# asserts the accounts module's OWN owner scope.
# =============================================================================

def _mk_account(owner, client_account, name):
    acc = CompanyAccount(company_name=name, has_buying_decision=True, account_owner=owner)
    acc.save(user=owner, client_id=client_account.id)
    return acc


def _acc_qs(client_account):
    return CompanyAccount.objects.filter(client_id=client_account.id)


@pytest.fixture
def acc_owner_a(db, client_account_a, role_individual_a):
    from end_users.models import User
    return User.objects.create(email='acc-owner-a@tenant-a.test', client_account=client_account_a,
                               role=role_individual_a, is_active=True)


@pytest.fixture
def acc_owner_b(db, client_account_a, role_individual_a):
    from end_users.models import User
    return User.objects.create(email='acc-owner-b@tenant-a.test', client_account=client_account_a,
                               role=role_individual_a, is_active=True)


@pytest.mark.django_db
class TestAccountOwnerScope:

    def test_mine_sees_own_account_not_others(self, acc_owner_a, acc_owner_b, client_account_a):
        acc_a = _mk_account(acc_owner_a, client_account_a, 'Owner A Corp (scope)')
        acc_b = _mk_account(acc_owner_b, client_account_a, 'Owner B Corp (scope)')
        scoped = apply_role_scope(
            _acc_qs(client_account_a), module='accounts', scope='mine',
            auth_ctx=_ctx(acc_owner_a, client_account_a),
        )
        ids = set(scoped.values_list('id', flat=True))
        assert acc_a.id in ids          # owner sees their own account
        assert acc_b.id not in ids      # NOT another owner's account
        assert scoped.count() == 1      # non-empty regression guard (not 0=none-bug, not 2=all)

    def test_manager_team_scope_sees_members_account(self, client_account_a, role_individual_a):
        from end_users.models import User, Team

        manager = User.objects.create(email='acc-mgr@tenant-a.test', client_account=client_account_a,
                                      role=role_individual_a, is_active=True)
        team = Team.objects.create(name='Team Acc', client_account=client_account_a, manager=manager)
        member = User.objects.create(email='acc-member@tenant-a.test', client_account=client_account_a,
                                     role=role_individual_a, is_active=True, team=team)
        outsider = User.objects.create(email='acc-out@tenant-a.test', client_account=client_account_a,
                                       role=role_individual_a, is_active=True)

        acc_member = _mk_account(member, client_account_a, 'Member Corp (scope)')
        acc_outsider = _mk_account(outsider, client_account_a, 'Outsider Corp (scope)')

        scoped = apply_role_scope(
            _acc_qs(client_account_a), module='accounts', scope='team',
            auth_ctx=_ctx(manager, client_account_a),
        )
        ids = set(scoped.values_list('id', flat=True))
        assert acc_member.id in ids        # manager sees their team member's account (account_owner__team_id)
        assert acc_outsider.id not in ids  # NOT an unrelated owner's account

    def test_client_scope_sees_all_accounts(self, acc_owner_a, acc_owner_b, client_account_a):
        _mk_account(acc_owner_a, client_account_a, 'Owner A Corp (scope)')
        _mk_account(acc_owner_b, client_account_a, 'Owner B Corp (scope)')
        scoped = apply_role_scope(
            _acc_qs(client_account_a), module='accounts', scope='client',
            auth_ctx=_ctx(acc_owner_a, client_account_a),
        )
        assert scoped.count() == 2  # client scope = whole tenant, no owner filter


# =============================================================================
# TEAM OWNER SCOPE — guardrail for the OWNERSHIP_MAP['teams'] fix
# (owner_user='manager', assigned_to_user='manager', created_by='-',
#  client_account_fk='client_account'). Team is a SENSITIVE org-structure model:
# the previous entry used '_id' attnames ('manager_id', 'created_by_id') that
# _is_valid_field rejects. Symptoms were the WORST of the attname family:
#   - mine  -> no valid ownership term -> _apply_mine_scope returns none() (deny)
#   - team  -> no valid term -> _apply_team_scope leaves the queryset UNCHANGED
#              = every team in the tenant (intra-tenant OVER-EXPOSURE)
# Reachable in production: TeamViewSet uses ScopedQuerysetMixin. Pre-existing,
# not a sprint regression. Locked here like territories/sales_quotas/accounts.
# =============================================================================

def _mk_team(manager, client_account, name):
    from end_users.models import Team
    return Team.objects.create(name=name, client_account=client_account, manager=manager)


def _team_qs(client_account):
    from end_users.models import Team
    return Team.objects.filter(client_account_id=client_account.id)


@pytest.fixture
def team_mgr_a(db, client_account_a, role_individual_a):
    from end_users.models import User
    return User.objects.create(email='team-mgr-a@tenant-a.test', client_account=client_account_a,
                               role=role_individual_a, is_active=True)


@pytest.fixture
def team_mgr_b(db, client_account_a, role_individual_a):
    from end_users.models import User
    return User.objects.create(email='team-mgr-b@tenant-a.test', client_account=client_account_a,
                               role=role_individual_a, is_active=True)


@pytest.mark.django_db
class TestTeamOwnerScope:

    def test_mine_sees_own_team_not_others(self, team_mgr_a, team_mgr_b, client_account_a):
        team_a = _mk_team(team_mgr_a, client_account_a, 'Team A (scope)')
        team_b = _mk_team(team_mgr_b, client_account_a, 'Team B (scope)')
        scoped = apply_role_scope(
            _team_qs(client_account_a), module='teams', scope='mine',
            auth_ctx=_ctx(team_mgr_a, client_account_a),
        )
        ids = set(scoped.values_list('id', flat=True))
        assert team_a.id in ids          # manager sees the team they manage
        assert team_b.id not in ids      # NOT a team managed by someone else
        assert scoped.count() == 1       # non-empty regression guard (not 0=none-bug, not 2=all)

    def test_team_scope_excludes_unrelated_teams_overexposure_guard(
        self, team_mgr_a, team_mgr_b, client_account_a
    ):
        """THE over-exposure guard. Before the fix, team scope had no valid
        ownership term, so _apply_team_scope returned the queryset UNCHANGED =
        every team in the tenant. Assert the manager sees only the team(s) in
        their own hierarchy, not an unrelated manager's team."""
        team_a = _mk_team(team_mgr_a, client_account_a, 'Team A (scope)')
        team_b = _mk_team(team_mgr_b, client_account_a, 'Team B (scope)')
        scoped = apply_role_scope(
            _team_qs(client_account_a), module='teams', scope='team',
            auth_ctx=_ctx(team_mgr_a, client_account_a),
        )
        ids = set(scoped.values_list('id', flat=True))
        assert team_a.id in ids          # own managed team
        assert team_b.id not in ids      # NOT an unrelated manager's team (exposed before fix)
        assert scoped.count() == 1       # exactly the hierarchy team — not 2 (over-exposure)

    def test_client_scope_sees_all_teams(self, team_mgr_a, team_mgr_b, client_account_a):
        _mk_team(team_mgr_a, client_account_a, 'Team A (scope)')
        _mk_team(team_mgr_b, client_account_a, 'Team B (scope)')
        scoped = apply_role_scope(
            _team_qs(client_account_a), module='teams', scope='client',
            auth_ctx=_ctx(team_mgr_a, client_account_a),
        )
        assert scoped.count() == 2  # client scope = whole tenant, no owner filter
