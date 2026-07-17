# backend/tests/bi/test_kpi_territory_by_team.py
"""
KPI 4b — territory coverage AGGREGATED by team (the manager Home).

Territories have no stored membership, so the aggregate can't be one GROUP BY
over a through-table like campaigns. Each territory's coverage counts are
materialised on the row (the lazy 2h snapshot) and this KPI SUMs them per team.

Proves:
- per-team % is account-weighted (SUM(num)/SUM(den)) + the global;
- global == sum of the team rows (ONE owner per territory -> no inter-team
  sharing -> NOT the campaign case, so no "counts once" and no tooltip);
- an account in TWO territories counts twice in the team sum — a documented
  NON-REGRESSION (today's per-territory ratios already count it independently);
- coherence: the aggregate % for a team's single territory == the LIVE
  territory_coverage for that territory (snapshot and live core agree);
- scope positive AND negative (an unmanaged team / another tenant -> absent);
- the query count is CONSTANT from 1 to N territories when snapshots are FRESH
  (the anti-explosion, the whole point), and a STALE read does bounded extra
  work (the per-refresh budget bound itself is proven in test_territory_snapshot);
- the LIVE per-territory KPI is unchanged (the rep sees nothing move).
"""

import pytest
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from app_modules.accounts.models import CompanyAccount, AccountClassification
from app_modules.activities.constants import ActivityStatus, ActivityType, ActivityOutcome
from app_modules.activities.models import Activity
from app_modules.territories.models import Territory
from app_modules.bi import registry
from app_modules.bi.cache import cached_run
from app_modules.bi.definitions import load_all
from app_modules.bi.definitions.territory import (
    territory_coverage,
    territory_progress_by_team,
)
from permissions.compat import AuthContext


TODAY = timezone.now().date()


def _ctx(user, ca):
    return AuthContext(user_id=str(user.id), client_id=str(ca.id), is_authenticated=True)


def _mk_user(email, ca, role, **extra):
    from end_users.models import User
    return User.objects.create(email=email, client_account=ca, role=role, is_active=True, **extra)


def _mk_team(name, ca, manager=None):
    from end_users.models import Team
    return Team.objects.create(name=name, client_account=ca, manager=manager)


def _mk_account(name, owner, ca, classification=AccountClassification.SMB):
    acc = CompanyAccount(company_name=name, has_buying_decision=True,
                         account_owner=owner, classification=classification)
    acc.save(user=owner, client_id=ca.id)
    return acc


_seq = 0


def _mk_territory(owner, ca, fdef=None):
    global _seq
    _seq += 1
    t = Territory(name=f'T{_seq}', type='ACCOUNT', owner=owner,
                  filter_definition=fdef or {'classification': 'SMB'})
    t.save(user=owner, client_id=ca.id)
    return t


def _touch(account, owner, ca):
    a = Activity(title='t', activity_type=ActivityType.CALL,
                 status=ActivityStatus.COMPLETED, outcome=ActivityOutcome.SUCCESSFUL,
                 account=account, owner=owner, scheduled_date=TODAY)
    a.save(user=owner, client_id=ca.id)
    return a


@pytest.fixture(autouse=True)
def _flush(db):
    load_all()
    cache.clear()
    yield
    cache.clear()
    registry.clear()


@pytest.fixture
def org(db, client_account_a, role_individual_a):
    """mgr manages AMER + EMEA. amer_rep in AMER, emea_rep in EMEA. ext_rep on an
    UNMANAGED team (APAC)."""
    ca = client_account_a
    mgr = _mk_user('t-mgr@a.test', ca, role_individual_a)
    amer = _mk_team('AMER', ca, manager=mgr)
    emea = _mk_team('EMEA', ca, manager=mgr)
    other = _mk_team('APAC', ca)
    return {
        'ca': ca, 'mgr': mgr, 'amer': amer, 'emea': emea, 'other': other,
        'amer_rep': _mk_user('t-amer@a.test', ca, role_individual_a, team=amer),
        'emea_rep': _mk_user('t-emea@a.test', ca, role_individual_a, team=emea),
        'ext_rep': _mk_user('t-ext@a.test', ca, role_individual_a, team=other),
    }


@pytest.mark.django_db
class TestByTeam:

    def test_account_weighted_per_team_and_global(self, org):
        ca = org['ca']
        C = AccountClassification
        # A territory filter matches accounts tenant-wide (it is NOT auto-scoped
        # to the owner), so we partition by classification to get DISJOINT sets.
        # AMER: {SMB} -> 4 SMB, 3 touched -> 3/4.
        _mk_territory(org['amer_rep'], ca, {'classification': 'SMB'})
        for i in range(4):
            acc = _mk_account(f'amer{i}', org['amer_rep'], ca, classification=C.SMB)
            if i < 3:
                _touch(acc, org['amer_rep'], ca)
        # EMEA: two DISJOINT territories -> account-weighted (1/1)+(1/3)=2/4.
        _mk_territory(org['emea_rep'], ca, {'classification': 'MIDMARKET'})
        _touch(_mk_account('emea-mm', org['emea_rep'], ca, classification=C.MIDMARKET),
               org['emea_rep'], ca)                                              # 1/1
        _mk_territory(org['emea_rep'], ca, {'classification': 'ENTERPRISE'})
        for i in range(3):
            acc = _mk_account(f'emea-ent{i}', org['emea_rep'], ca, classification=C.ENTERPRISE)
            if i == 0:
                _touch(acc, org['emea_rep'], ca)                                 # 1/3

        res = cached_run(territory_progress_by_team, _ctx(org['mgr'], ca), scope='team')
        amer, emea = str(org['amer'].id), str(org['emea'].id)
        assert res.value[amer] == 75.0                       # 3/4
        assert res.value[emea] == 50.0                       # (1+1)/(1+3), weighted
        assert res.meta['labels'][amer] == 'AMER'
        # global = (3+2)/(4+4) = 62.5, and == the plain sum of the team rows.
        assert res.meta['global'] == {'total': 8, 'done': 5, 'progress_pct': 62.5}
        per_team_total = sum(g['total'] for g in res.meta['per_group'].values())
        assert res.meta['global']['total'] == per_team_total   # NO inter-team sharing

    def test_account_in_two_territories_counts_twice_non_regression(self, org):
        """One account in TWO territories of the same team is summed twice — the
        SAME as today's two independent per-territory ratios. Documented, not a
        bug introduced by the aggregate."""
        ca = org['ca']
        # two territories, same filter, same owner -> the one SMB account is in both
        _mk_territory(org['amer_rep'], ca, {'classification': 'SMB'})
        _mk_territory(org['amer_rep'], ca, {'classification': 'SMB'})
        _mk_account('shared', org['amer_rep'], ca)  # SMB, matches BOTH

        res = cached_run(territory_progress_by_team, _ctx(org['mgr'], ca), scope='team')
        amer = str(org['amer'].id)
        # denominator sums the account once PER territory -> 2, not 1.
        assert res.meta['per_group'][amer]['total'] == 2

    def test_coherence_with_live_per_territory(self, org):
        """The aggregate % for a team's single territory == the LIVE
        territory_coverage for that territory (snapshot and live core agree)."""
        ca = org['ca']
        terr = _mk_territory(org['amer_rep'], ca)
        for i in range(4):
            acc = _mk_account(f'c{i}', org['amer_rep'], ca)
            if i < 3:
                _touch(acc, org['amer_rep'], ca)  # 3/4 = 75

        agg = cached_run(territory_progress_by_team, _ctx(org['mgr'], ca), scope='team')
        live = cached_run(territory_coverage, _ctx(org['mgr'], ca), scope='team',
                          params={'territory_id': str(terr.id)})
        assert agg.value[str(org['amer'].id)] == live.value == 75.0

    def test_scope_negative_unmanaged_team_and_cross_tenant(
        self, org, client_account_b, role_individual_b
    ):
        ca = org['ca']
        # a territory entirely under APAC (unmanaged by mgr)
        _mk_territory(org['ext_rep'], ca)
        _mk_account('apac', org['ext_rep'], ca)
        res = cached_run(territory_progress_by_team, _ctx(org['mgr'], ca), scope='team')
        assert str(org['other'].id) not in res.value
        assert res.value == {}  # nothing in the manager's hierarchy

        ub = _mk_user('t-ub@b.test', client_account_b, role_individual_b)
        res_b = cached_run(territory_progress_by_team, _ctx(ub, client_account_b), scope='team')
        assert res_b.value == {}


@pytest.mark.django_db
class TestQueryBound:

    def _prime(self, org, ca):
        # Clear first: a warm 30s cache would make this HIT and skip the refresh,
        # leaving new snapshots stale (and paid for during measurement).
        cache.clear()
        cached_run(territory_progress_by_team, _ctx(org['mgr'], ca), scope='client')

    def _measure(self, org, ca):
        cache.clear()
        with CaptureQueriesContext(connection) as cap:
            _ = cached_run(territory_progress_by_team, _ctx(org['mgr'], ca), scope='client').value
        return len(cap.captured_queries)

    def test_query_count_constant_when_snapshots_fresh(self, org):
        """1 vs 11 fresh territories -> identical query count (no per-territory
        query). The anti-explosion, the pendant of the campaign O(1) test."""
        ca = org['ca']
        _mk_territory(org['amer_rep'], ca)
        _mk_account('a0', org['amer_rep'], ca)
        self._prime(org, ca)         # refresh the 1
        n1 = self._measure(org, ca)  # snapshots fresh

        for i in range(10):
            _mk_territory(org['amer_rep'], ca)
            _mk_account(f'more{i}', org['amer_rep'], ca)
        self._prime(org, ca)         # refresh the 10 new
        n11 = self._measure(org, ca)  # 11 snapshots fresh

        assert n1 == n11  # constant in the number of territories

    def test_stale_read_does_bounded_extra_work_then_settles(self, org):
        """A stale read recomputes snapshots (more queries); the next read, now
        fresh, is back to the constant. (The per-refresh budget cap itself is
        proven in test_territory_snapshot.)"""
        ca = org['ca']
        C = AccountClassification
        # 3 DISJOINT territories (one account each), none touched -> 3 total, 0 done.
        for cls in ('SMB', 'MIDMARKET', 'ENTERPRISE'):
            _mk_territory(org['amer_rep'], ca, {'classification': cls})
            _mk_account(f's-{cls}', org['amer_rep'], ca, classification=getattr(C, cls))

        cache.clear()
        with CaptureQueriesContext(connection) as cold:
            v1 = cached_run(territory_progress_by_team, _ctx(org['mgr'], ca), scope='client')
        stale_count = len(cold.captured_queries)

        fresh_count = self._measure(org, ca)  # snapshots now fresh
        assert stale_count > fresh_count      # the stale read paid the recompute
        # and the value is correct once materialised (3 territories, 0 touched).
        assert v1.meta['global'] == {'total': 3, 'done': 0, 'progress_pct': 0.0}


@pytest.mark.django_db
def test_live_per_territory_kpi_unchanged(org):
    """The rep's live territory_coverage still returns the fresh truth,
    untouched by the aggregate/snapshot machinery."""
    ca = org['ca']
    terr = _mk_territory(org['amer_rep'], ca)
    for i in range(2):
        acc = _mk_account(f'l{i}', org['amer_rep'], ca)
        if i == 0:
            _touch(acc, org['amer_rep'], ca)  # 1/2 = 50
    res = cached_run(territory_coverage, _ctx(org['amer_rep'], ca), scope='mine',
                     params={'territory_id': str(terr.id)})
    assert res.value == 50.0
    assert res.meta['numerator'] == 1 and res.meta['denominator'] == 2
