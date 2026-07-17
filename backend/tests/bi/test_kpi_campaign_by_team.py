# backend/tests/bi/test_kpi_campaign_by_team.py
"""
KPI 2b/2c — campaign progress AGGREGATED by team / by owner (the manager Home).

The manager Home can't fire one campaign_progress per campaign (200 -> 200
requests). These KPIs return the aggregate in ONE grouped query, fanning each
per-campaign row out to BOTH its owner and executor group (a campaign is the
work of whoever executes it AND the result of whoever owns it).

Proves:
- per-team % is account-weighted (SUM(done)/SUM(total)), STOPPED counts as done;
- a SHARED campaign (owner + executor both managed) lands in both buckets, and
  the GLOBAL counts it ONCE -> global total < sum of per-team totals (pinned so
  nobody "fixes" it);
- owner-external / executor-internal appears ONLY in the executor's managed
  bucket for this manager (the PO's rule);
- owner == executor is deduped (one bucket, not doubled);
- coherence: the aggregate % for a team's single campaign == campaign_progress
  for that campaign (shared CAMPAIGN_DONE_Q -> rep & manager never disagree);
- by_owner counts a campaign for owner AND executor, roster-filtered;
- scope positive AND negative (out-of-hierarchy team, cross-tenant);
- assertNumQueries: the aggregate is O(1) in the number of campaigns;
- CACHE invalidation: a CampaignAccount status write (the activity-completion
  cascade's effect) bumps the campaigns tag -> the aggregate recomputes.
"""

import pytest
from django.core.cache import cache

from app_modules.accounts.models import CompanyAccount
from app_modules.campaigns.constants import CampaignAccountStatus, CampaignStatus
from app_modules.campaigns.models.campaign import Campaign
from app_modules.campaigns.models.campaign_account import CampaignAccount
from app_modules.bi import registry
from app_modules.bi.cache import cached_run
from app_modules.bi.definitions import load_all
from app_modules.bi.definitions.campaigns import (
    campaign_progress,
    campaign_progress_by_owner,
    campaign_progress_by_team,
)
from app_modules.bi.signals import cache_invalidation as ci
from permissions.compat import AuthContext

from datetime import timedelta
from django.utils import timezone

TODAY = timezone.now().date()


def _ctx(user, ca):
    return AuthContext(user_id=str(user.id), client_id=str(ca.id), is_authenticated=True)


def _mk_user(email, ca, role, **extra):
    from end_users.models import User
    return User.objects.create(email=email, client_account=ca, role=role, is_active=True, **extra)


def _mk_team(name, ca, manager=None):
    from end_users.models import Team
    return Team.objects.create(name=name, client_account=ca, manager=manager)


def _mk_account(name, owner, ca):
    acc = CompanyAccount(company_name=name, has_buying_decision=True, account_owner=owner)
    acc.save(user=owner, client_id=ca.id)
    return acc


def _mk_campaign(owner, ca, executor=None):
    c = Campaign(name='Camp', campaign_type='OUTBOUND', owner=owner, executor=executor,
                 status=CampaignStatus.ACTIVE,
                 planned_start_date=TODAY, planned_end_date=TODAY + timedelta(days=30))
    c.save(user=owner, client_id=ca.id)
    return c


def _mk_ca(campaign, ca, statuses):
    """Create len(statuses) CampaignAccounts on `campaign` with the given statuses."""
    for i, st in enumerate(statuses):
        acc = _mk_account(f'{campaign.id}-{i}', campaign.owner, ca)
        CampaignAccount(campaign=campaign, account=acc, status=st).save(
            user=campaign.owner, client_id=ca.id)


@pytest.fixture(autouse=True)
def _flush(db):
    load_all()
    cache.clear()
    yield
    cache.clear()
    registry.clear()


@pytest.fixture
def org(db, client_account_a, role_individual_a):
    """mgr manages AMER + EMEA. amer_rep in AMER, emea_rep in EMEA. ext_rep is on
    an UNMANAGED team (mgr does not manage it)."""
    ca = client_account_a
    mgr = _mk_user('mgr@a.test', ca, role_individual_a)
    amer = _mk_team('AMER', ca, manager=mgr)
    emea = _mk_team('EMEA', ca, manager=mgr)
    other = _mk_team('APAC', ca)  # not managed by mgr
    return {
        'ca': ca, 'mgr': mgr, 'amer': amer, 'emea': emea, 'other': other,
        'amer_rep': _mk_user('amer@a.test', ca, role_individual_a, team=amer),
        'emea_rep': _mk_user('emea@a.test', ca, role_individual_a, team=emea),
        'ext_rep': _mk_user('ext@a.test', ca, role_individual_a, team=other),
    }


# =============================================================================
# BY TEAM — the manager's first level
# =============================================================================

@pytest.mark.django_db
class TestByTeam:

    def test_account_weighted_and_stopped_as_done(self, org):
        ca = org['ca']
        # AMER: campaign with 2 COMPLETED + 1 STOPPED + 1 PENDING = 3 done / 4.
        c1 = _mk_campaign(org['amer_rep'], ca)
        _mk_ca(c1, ca, [CampaignAccountStatus.COMPLETED, CampaignAccountStatus.COMPLETED,
                        CampaignAccountStatus.STOPPED, CampaignAccountStatus.PENDING])
        # EMEA: two campaigns of different sizes -> account-weighted SUM/SUM.
        c2 = _mk_campaign(org['emea_rep'], ca)
        _mk_ca(c2, ca, [CampaignAccountStatus.COMPLETED])                       # 1/1
        c3 = _mk_campaign(org['emea_rep'], ca)
        _mk_ca(c3, ca, [CampaignAccountStatus.PENDING, CampaignAccountStatus.PENDING,
                        CampaignAccountStatus.COMPLETED])                        # 1/3
        res = cached_run(campaign_progress_by_team, _ctx(org['mgr'], ca), scope='team')

        amer, emea = str(org['amer'].id), str(org['emea'].id)
        assert res.value[amer] == 75.0                 # 3/4, STOPPED counted done
        # EMEA weighted: (1+1)/(1+3) = 50.0, NOT avg(100, 33.3)
        assert res.value[emea] == 50.0
        assert res.meta['labels'][amer] == 'AMER'
        # global = 5 done / 8 total
        assert res.meta['global'] == {'total': 8, 'done': 5, 'progress_pct': 62.5}

    def test_shared_campaign_global_counts_once(self, org):
        """A campaign owned by AMER, executed by EMEA (both managed) -> both
        buckets; the GLOBAL counts it once, so global total < AMER+EMEA totals."""
        ca = org['ca']
        c = _mk_campaign(org['amer_rep'], ca, executor=org['emea_rep'])
        _mk_ca(c, ca, [CampaignAccountStatus.COMPLETED, CampaignAccountStatus.PENDING])  # 1/2
        res = cached_run(campaign_progress_by_team, _ctx(org['mgr'], ca), scope='team')

        amer, emea = str(org['amer'].id), str(org['emea'].id)
        # same campaign in both buckets, identical numbers
        assert res.meta['per_group'][amer] == {'total': 2, 'done': 1, 'progress_pct': 50.0}
        assert res.meta['per_group'][emea] == {'total': 2, 'done': 1, 'progress_pct': 50.0}
        # GLOBAL counts the campaign ONCE (2, not 4)
        assert res.meta['global']['total'] == 2
        per_team_total = sum(g['total'] for g in res.meta['per_group'].values())
        assert per_team_total == 4                     # sum of team rows double-counts
        assert res.meta['global']['total'] < per_team_total  # THE pinned invariant

    def test_owner_external_executor_internal(self, org):
        """Owned by an unmanaged rep, executed by a managed rep -> appears ONLY
        in the executor's managed team bucket for THIS manager."""
        ca = org['ca']
        c = _mk_campaign(org['ext_rep'], ca, executor=org['emea_rep'])  # owner APAC, exec EMEA
        _mk_ca(c, ca, [CampaignAccountStatus.COMPLETED, CampaignAccountStatus.PENDING])
        res = cached_run(campaign_progress_by_team, _ctx(org['mgr'], ca), scope='team')

        assert str(org['emea'].id) in res.value        # executor's team surfaced
        assert str(org['other'].id) not in res.value   # owner's external team dropped
        assert res.meta['global']['total'] == 2        # still counts (via executor)

    def test_owner_equals_executor_deduped(self, org):
        ca = org['ca']
        rep = org['amer_rep']
        c = _mk_campaign(rep, ca, executor=rep)         # same person
        _mk_ca(c, ca, [CampaignAccountStatus.COMPLETED, CampaignAccountStatus.PENDING])
        res = cached_run(campaign_progress_by_team, _ctx(org['mgr'], ca), scope='team')
        # one bucket, not doubled
        assert res.meta['per_group'][str(org['amer'].id)]['total'] == 2

    def test_coherence_with_per_campaign(self, org):
        """The aggregate % for a team's single campaign == campaign_progress for
        that campaign (shared CAMPAIGN_DONE_Q -> no contradiction)."""
        ca = org['ca']
        c = _mk_campaign(org['amer_rep'], ca)
        _mk_ca(c, ca, [CampaignAccountStatus.COMPLETED, CampaignAccountStatus.STOPPED,
                       CampaignAccountStatus.PENDING])           # 2/3 = 66.7
        agg = cached_run(campaign_progress_by_team, _ctx(org['mgr'], ca), scope='team')
        per = cached_run(campaign_progress, _ctx(org['mgr'], ca), scope='team',
                         params={'campaign_id': str(c.id)})
        assert agg.value[str(org['amer'].id)] == per.value == 66.7

    def test_scope_negative_other_manager_and_cross_tenant(
        self, org, client_account_b, role_individual_b
    ):
        ca = org['ca']
        # a campaign entirely under APAC (unmanaged by mgr, and owner not in scope)
        c = _mk_campaign(org['ext_rep'], ca)
        _mk_ca(c, ca, [CampaignAccountStatus.COMPLETED])
        res = cached_run(campaign_progress_by_team, _ctx(org['mgr'], ca), scope='team')
        assert str(org['other'].id) not in res.value
        assert res.value == {}  # nothing in the manager's hierarchy

        # cross-tenant: a user of tenant B sees none of tenant A
        ub = _mk_user('ub@b.test', client_account_b, role_individual_b)
        res_b = cached_run(campaign_progress_by_team, _ctx(ub, client_account_b), scope='team')
        assert res_b.value == {}


# =============================================================================
# BY OWNER — the "who's behind" drill-down
# =============================================================================

@pytest.mark.django_db
class TestByOwner:

    def test_counts_for_owner_and_executor_roster_filtered(self, org):
        ca = org['ca']
        # owned by ext_rep (out of roster), executed by emea_rep (in roster)
        c = _mk_campaign(org['ext_rep'], ca, executor=org['emea_rep'])
        _mk_ca(c, ca, [CampaignAccountStatus.COMPLETED, CampaignAccountStatus.PENDING])
        res = cached_run(campaign_progress_by_owner, _ctx(org['mgr'], ca), scope='team')

        assert str(org['emea_rep'].id) in res.value     # executor (in roster) surfaced
        assert str(org['ext_rep'].id) not in res.value  # external owner dropped
        assert res.meta['dimension'] == 'owner'


# =============================================================================
# PERF — the whole point: O(1) in the number of campaigns
# =============================================================================

@pytest.mark.django_db
class TestQueryBound:

    def test_aggregate_is_two_queries_client_scope(self, org, django_assert_num_queries):
        ca = org['ca']
        for _ in range(3):
            c = _mk_campaign(org['amer_rep'], ca)
            _mk_ca(c, ca, [CampaignAccountStatus.COMPLETED, CampaignAccountStatus.PENDING])
        # client scope skips managed-team resolution -> just aggregate + labels.
        with django_assert_num_queries(2):
            res = cached_run(campaign_progress_by_team, _ctx(org['mgr'], ca), scope='client')
            _ = res.value

    def test_query_count_does_not_grow_with_campaigns(self, org, django_assert_num_queries):
        ca = org['ca']
        _mk_ca(_mk_campaign(org['amer_rep'], ca), ca, [CampaignAccountStatus.COMPLETED])
        with django_assert_num_queries(2):
            _ = cached_run(campaign_progress_by_team, _ctx(org['mgr'], ca), scope='client').value
        cache.clear()
        for _ in range(10):
            _mk_ca(_mk_campaign(org['amer_rep'], ca), ca, [CampaignAccountStatus.PENDING])
        with django_assert_num_queries(2):  # same count with 11 campaigns
            _ = cached_run(campaign_progress_by_team, _ctx(org['mgr'], ca), scope='client').value


# =============================================================================
# CACHE — the aggregate must EXPIRE (not "never invalidate")
# =============================================================================

@pytest.mark.django_db
class TestInvalidation:

    def test_campaign_account_write_bumps_the_tag(
        self, org, django_capture_on_commit_callbacks
    ):
        """A CampaignAccount status change — the activity-completion cascade's
        effect — bumps the campaigns tag so the cached aggregate recomputes."""
        ca = org['ca']
        c = _mk_campaign(org['amer_rep'], ca)
        acc = _mk_account('to-complete', org['amer_rep'], ca)
        cc = CampaignAccount(campaign=c, account=acc, status=CampaignAccountStatus.PENDING)
        cc.save(user=org['amer_rep'], client_id=ca.id)

        ci.connect_invalidation_receivers()
        try:
            amer = str(org['amer'].id)
            v1 = cached_run(campaign_progress_by_team, _ctx(org['mgr'], ca), scope='team')
            assert v1.value[amer] == 0.0  # 0/1 done

            # the cascade's effect: the CampaignAccount moves to a final state.
            # Execute the on_commit invalidation callback (bumps the campaigns tag).
            with django_capture_on_commit_callbacks(execute=True) as callbacks:
                cc.status = CampaignAccountStatus.COMPLETED
                cc.save(user=org['amer_rep'], client_id=ca.id)
            assert callbacks, "expected an on_commit invalidation callback"

            v2 = cached_run(campaign_progress_by_team, _ctx(org['mgr'], ca), scope='team')
            assert v2.value[amer] == 100.0  # recomputed -> cache DID expire
        finally:
            ci.disconnect_invalidation_receivers()
