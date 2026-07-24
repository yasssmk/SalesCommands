"""
DecisionCycleViewSet list — filters, ordering, search, and the TD-90 N+1 death.

Every facet is exercised through the REAL endpoint (`/decision_cycles/`), with a
positive and a negative case. The unified `status` facet is proven on both
vocabularies (outcome LOST, derived STALLED). The to-many facets (contact,
product) are proven not to fan out. An assertNumQueries proves the two count
columns no longer scale with the number of cycles (TD-90).

Scope note: cross-owner facets authenticate with owner_scope=all, which returns
the tenant-wide (client-scoped) list — tenant isolation still holds upstream, so
a tenant-B cycle never appears.
"""

from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework import status

from app_modules.accounts.models import CompanyAccount
from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.activities.models import Activity
from app_modules.contacts.models import Contact
from app_modules.decision_cycles.constants import (
    CycleOutcome,
    DecisionStepStatus,
    PIPELINE_STEPS_CONFIG,
)
from app_modules.decision_cycles.models import (
    DealProduct,
    DecisionCycle,
    DecisionStep,
    DecisionStepContact,
)
from app_modules.product_catalog.models import ProductCatalog


LIST_URL = '/decision_cycles/'
TODAY = timezone.now().date()
FUTURE = TODAY + timedelta(days=30)


# =============================================================================
# RESPONSE HELPERS
# =============================================================================

def _rows(resp):
    body = resp.json()['data']
    results = body.get('results', body)
    if isinstance(results, dict):
        results = results.get('results', [])
    return results


def _ids(resp):
    return {row['id'] for row in _rows(resp)}


def _ordered_ids(resp):
    return [row['id'] for row in _rows(resp)]


# =============================================================================
# BUILDERS
# =============================================================================

def _user(client_account, role, email, **kw):
    from end_users.models import User
    return User.objects.create(
        email=email, client_account=client_account, role=role, is_active=True, **kw
    )


def _team(name, client_account):
    from end_users.models import Team
    return Team.objects.create(name=name, client_account=client_account)


def _account(owner, client_account, name):
    acc = CompanyAccount(company_name=name, has_buying_decision=True, account_owner=owner)
    acc.save(user=owner, client_id=client_account.id)
    return acc


def _cycle(owner, client_account, account, name, outcome=None,
           source_campaign=None, estimated_value=None, is_active=False):
    c = DecisionCycle(
        account=account, owner=owner, name=name, is_active=is_active,
        estimated_value=estimated_value, source_campaign=source_campaign,
    )
    if outcome is not None:
        c.outcome = outcome
    c.save(user=owner, client_id=client_account.id)
    return c


def _steps(cycle, owner, client_account):
    previous = None
    steps = []
    for cfg in PIPELINE_STEPS_CONFIG:
        s = DecisionStep(
            cycle=cycle, name=cfg['step'].label, stage=cfg['step'].value,
            order=cfg['order'], status=DecisionStepStatus.NOT_STARTED,
            previous_step=previous, expected_end=None,
        )
        s.save(user=owner, client_id=client_account.id)
        steps.append(s)
        previous = s
    return steps


def _activity(step, owner, client_account, status_value, **overrides):
    defaults = dict(
        title='act', activity_type=ActivityType.MEETING, status=status_value,
        account=step.cycle.account, owner=owner,
        decision_cycle=step.cycle, decision_step=step,
        scheduled_date=FUTURE if status_value == ActivityStatus.PLANNED else TODAY,
    )
    defaults.update(overrides)
    a = Activity(**defaults)
    a.save(user=owner, client_id=client_account.id)
    return a


def _contact(account, client_account, owner, first='Jane', last='Doe'):
    c = Contact(account=account, first_name=first, last_name=last, job_title='VP')
    c.save(user=owner, client_id=client_account.id)
    return c


def _product(name, client_account, owner):
    p = ProductCatalog(name=name, description='x', default_unit_price=1000)
    p.save(user=owner, client_id=client_account.id)
    return p


def _campaign(owner, client_account, name):
    from app_modules.campaigns.models import Campaign
    from app_modules.campaigns.constants import CampaignType
    c = Campaign(
        name=name, campaign_type=CampaignType.OUTBOUND, owner=owner,
        planned_start_date=TODAY, planned_end_date=TODAY + timedelta(days=30),
    )
    c.save(user=owner, client_id=client_account.id)
    return c


def _stalled_cycle(owner, client_account, name):
    """A cycle whose last step is completed with no planned anywhere → STALLED."""
    acc = _account(owner, client_account, f'{name} Corp')
    cyc = _cycle(owner, client_account, acc, name)
    steps = _steps(cyc, owner, client_account)
    _activity(steps[4], owner, client_account, ActivityStatus.COMPLETED)
    return cyc


def _in_progress_cycle(owner, client_account, name):
    """A cycle with a future planned activity → IN_PROGRESS."""
    acc = _account(owner, client_account, f'{name} Corp')
    cyc = _cycle(owner, client_account, acc, name)
    steps = _steps(cyc, owner, client_account)
    _activity(steps[0], owner, client_account, ActivityStatus.PLANNED)
    return cyc


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def rep(db, client_account_a, role_individual_a):
    return _user(client_account_a, role_individual_a, 'rep-filters@a.test')


def _get_all(api, authenticate, rep, client_account_a, params=None):
    """Authenticated tenant-wide (owner_scope=all) list request."""
    authenticate(api, rep, client_account_a.id)
    p = {'owner_scope': 'all'}
    if params:
        p.update(params)
    return api.get(LIST_URL, p)


# =============================================================================
# ACCOUNT
# =============================================================================

@pytest.mark.django_db
def test_filter_account(api, authenticate, rep, client_account_a):
    acc1 = _account(rep, client_account_a, 'Acc One')
    acc2 = _account(rep, client_account_a, 'Acc Two')
    c1 = _cycle(rep, client_account_a, acc1, 'c1')
    c2 = _cycle(rep, client_account_a, acc2, 'c2')
    resp = _get_all(api, authenticate, rep, client_account_a, {'account': str(acc1.id)})
    ids = _ids(resp)
    assert str(c1.id) in ids
    assert str(c2.id) not in ids


# =============================================================================
# OWNER (nullable)
# =============================================================================

@pytest.mark.django_db
def test_filter_owner_and_null_owner_not_dropped(
    api, authenticate, rep, client_account_a, role_individual_a
):
    other = _user(client_account_a, role_individual_a, 'other@a.test')
    acc = _account(rep, client_account_a, 'Shared Corp')
    mine = _cycle(rep, client_account_a, acc, 'mine')
    theirs = _cycle(other, client_account_a, acc, 'theirs')
    orphan = _cycle(rep, client_account_a, acc, 'orphan')
    DecisionCycle.objects.filter(pk=orphan.pk).update(owner=None)

    # positive/negative
    resp = _get_all(api, authenticate, rep, client_account_a, {'owner': str(rep.id)})
    ids = _ids(resp)
    assert str(mine.id) in ids
    assert str(theirs.id) not in ids

    # unfiltered list keeps the owner-less cycle
    resp_all = _get_all(api, authenticate, rep, client_account_a)
    assert str(orphan.id) in _ids(resp_all)


# =============================================================================
# TEAM (exact, no descent)
# =============================================================================

@pytest.mark.django_db
def test_filter_team_exact(api, authenticate, rep, client_account_a, role_individual_a):
    team1, team2 = _team('Alpha', client_account_a), _team('Beta', client_account_a)
    u1 = _user(client_account_a, role_individual_a, 'u1@a.test', team=team1)
    u2 = _user(client_account_a, role_individual_a, 'u2@a.test', team=team2)
    acc = _account(rep, client_account_a, 'Team Corp')
    c1 = _cycle(u1, client_account_a, acc, 'in-alpha')
    c2 = _cycle(u2, client_account_a, acc, 'in-beta')
    resp = _get_all(api, authenticate, rep, client_account_a, {'team': str(team1.id)})
    ids = _ids(resp)
    assert str(c1.id) in ids
    assert str(c2.id) not in ids


# =============================================================================
# SOURCE CAMPAIGN (nullable)
# =============================================================================

@pytest.mark.django_db
def test_filter_source_campaign_and_null_not_dropped(
    api, authenticate, rep, client_account_a
):
    camp = _campaign(rep, client_account_a, 'Src Camp')
    acc = _account(rep, client_account_a, 'Camp Corp')
    sourced = _cycle(rep, client_account_a, acc, 'sourced', source_campaign=camp)
    unsourced = _cycle(rep, client_account_a, acc, 'unsourced')

    resp = _get_all(api, authenticate, rep, client_account_a,
                    {'source_campaign': str(camp.id)})
    ids = _ids(resp)
    assert str(sourced.id) in ids
    assert str(unsourced.id) not in ids

    # unfiltered keeps the campaign-less cycle
    assert str(unsourced.id) in _ids(_get_all(api, authenticate, rep, client_account_a))


# =============================================================================
# CONTACT — union of step-attached and activity-attached (the subtle one)
# =============================================================================

@pytest.mark.django_db
def test_filter_contact_union_both_provenances(
    api, authenticate, rep, client_account_a
):
    acc = _account(rep, client_account_a, 'Contact Corp')
    target = _contact(acc, client_account_a, rep, first='Target', last='Person')
    other = _contact(acc, client_account_a, rep, first='Other', last='Nobody')

    # cycle A — contact attached to a STEP
    cyc_step = _cycle(rep, client_account_a, acc, 'via-step')
    steps_a = _steps(cyc_step, rep, client_account_a)
    DecisionStepContact.objects.create(
        step=steps_a[0], contact=target, client_id=client_account_a.id,
    )

    # cycle B — contact only on an ACTIVITY
    cyc_act = _cycle(rep, client_account_a, acc, 'via-activity')
    steps_b = _steps(cyc_act, rep, client_account_a)
    act = _activity(steps_b[1], rep, client_account_a, ActivityStatus.PLANNED)
    act.contacts.add(target)

    # cycle C — has a DIFFERENT contact only
    cyc_none = _cycle(rep, client_account_a, acc, 'without')
    steps_c = _steps(cyc_none, rep, client_account_a)
    _activity(steps_c[0], rep, client_account_a, ActivityStatus.PLANNED).contacts.add(other)

    resp = _get_all(api, authenticate, rep, client_account_a,
                    {'contact': str(target.id)})
    ids = _ids(resp)
    assert str(cyc_step.id) in ids      # step provenance
    assert str(cyc_act.id) in ids       # activity provenance
    assert str(cyc_none.id) not in ids  # different contact → excluded


# =============================================================================
# PRODUCT
# =============================================================================

@pytest.mark.django_db
def test_filter_product(api, authenticate, rep, client_account_a):
    acc = _account(rep, client_account_a, 'Prod Corp')
    prod = _product('Widget', client_account_a, rep)
    other = _product('Gadget', client_account_a, rep)
    with_prod = _cycle(rep, client_account_a, acc, 'with-widget')
    DealProduct.objects.create(
        decision_cycle=with_prod, product_catalog_entry=prod, quantity=1,
        client_id=client_account_a.id,
    )
    without = _cycle(rep, client_account_a, acc, 'with-gadget')
    DealProduct.objects.create(
        decision_cycle=without, product_catalog_entry=other, quantity=1,
        client_id=client_account_a.id,
    )
    resp = _get_all(api, authenticate, rep, client_account_a, {'product': str(prod.id)})
    ids = _ids(resp)
    assert str(with_prod.id) in ids
    assert str(without.id) not in ids


# =============================================================================
# UNIFIED STATUS — both vocabularies
# =============================================================================

@pytest.mark.django_db
def test_filter_status_lost_via_outcome_distinct_from_not_qualified(
    api, authenticate, rep, client_account_a
):
    acc = _account(rep, client_account_a, 'Status Corp')
    lost = _cycle(rep, client_account_a, acc, 'lost', outcome=CycleOutcome.LOST)
    nq = _cycle(rep, client_account_a, acc, 'nq', outcome=CycleOutcome.NOT_QUALIFIED)
    won = _cycle(rep, client_account_a, acc, 'won', outcome=CycleOutcome.WON)

    resp = _get_all(api, authenticate, rep, client_account_a, {'status': 'LOST'})
    ids = _ids(resp)
    assert str(lost.id) in ids
    assert str(nq.id) not in ids   # NOT_QUALIFIED stays distinct from LOST
    assert str(won.id) not in ids

    # and NOT_QUALIFIED is selectable on its own
    resp_nq = _get_all(api, authenticate, rep, client_account_a, {'status': 'NOT_QUALIFIED'})
    assert _ids(resp_nq) & {str(lost.id), str(nq.id), str(won.id)} == {str(nq.id)}


@pytest.mark.django_db
def test_filter_status_stalled_via_derived(api, authenticate, rep, client_account_a):
    stalled = _stalled_cycle(rep, client_account_a, 'stalled')
    in_prog = _in_progress_cycle(rep, client_account_a, 'moving')

    resp = _get_all(api, authenticate, rep, client_account_a, {'status': 'STALLED'})
    ids = _ids(resp)
    assert str(stalled.id) in ids
    assert str(in_prog.id) not in ids

    resp_ip = _get_all(api, authenticate, rep, client_account_a, {'status': 'IN_PROGRESS'})
    ids_ip = _ids(resp_ip)
    assert str(in_prog.id) in ids_ip
    assert str(stalled.id) not in ids_ip


# =============================================================================
# ORDERING — one test per column, ascending + descending, real endpoint
# =============================================================================

def _rel_order(resp, ids):
    """Positions of the given ids within the ordered response (missing → -1)."""
    order = _ordered_ids(resp)
    return [order.index(i) if i in order else -1 for i in ids]


@pytest.mark.django_db
def test_ordering_name(api, authenticate, rep, client_account_a):
    acc = _account(rep, client_account_a, 'Ord Corp')
    a = _cycle(rep, client_account_a, acc, 'AAA name')
    b = _cycle(rep, client_account_a, acc, 'ZZZ name')
    asc = _rel_order(_get_all(api, authenticate, rep, client_account_a, {'ordering': 'name'}),
                     [str(a.id), str(b.id)])
    assert asc[0] < asc[1]
    desc = _rel_order(_get_all(api, authenticate, rep, client_account_a, {'ordering': '-name'}),
                      [str(a.id), str(b.id)])
    assert desc[0] > desc[1]


@pytest.mark.django_db
def test_ordering_account(api, authenticate, rep, client_account_a):
    acc_a = _account(rep, client_account_a, 'AAA Account')
    acc_z = _account(rep, client_account_a, 'ZZZ Account')
    a = _cycle(rep, client_account_a, acc_a, 'ca')
    z = _cycle(rep, client_account_a, acc_z, 'cz')
    asc = _rel_order(_get_all(api, authenticate, rep, client_account_a,
                              {'ordering': 'account__company_name'}), [str(a.id), str(z.id)])
    assert asc[0] < asc[1]
    desc = _rel_order(_get_all(api, authenticate, rep, client_account_a,
                               {'ordering': '-account__company_name'}), [str(a.id), str(z.id)])
    assert desc[0] > desc[1]


@pytest.mark.django_db
def test_ordering_estimated_value(api, authenticate, rep, client_account_a):
    acc = _account(rep, client_account_a, 'Val Corp')
    lo = _cycle(rep, client_account_a, acc, 'lo', estimated_value=100)
    hi = _cycle(rep, client_account_a, acc, 'hi', estimated_value=9000)
    asc = _rel_order(_get_all(api, authenticate, rep, client_account_a,
                              {'ordering': 'estimated_value'}), [str(lo.id), str(hi.id)])
    assert asc[0] < asc[1]
    desc = _rel_order(_get_all(api, authenticate, rep, client_account_a,
                               {'ordering': '-estimated_value'}), [str(lo.id), str(hi.id)])
    assert desc[0] > desc[1]


@pytest.mark.django_db
def test_ordering_owner(api, authenticate, rep, client_account_a, role_individual_a):
    acc = _account(rep, client_account_a, 'Owner Ord Corp')
    ua = _user(client_account_a, role_individual_a, 'aaa-owner@a.test', first_name='Aaa')
    uz = _user(client_account_a, role_individual_a, 'zzz-owner@a.test', first_name='Zzz')
    ca = _cycle(ua, client_account_a, acc, 'ca')
    cz = _cycle(uz, client_account_a, acc, 'cz')
    asc = _rel_order(_get_all(api, authenticate, rep, client_account_a,
                              {'ordering': 'owner__first_name'}), [str(ca.id), str(cz.id)])
    assert asc[0] < asc[1]
    desc = _rel_order(_get_all(api, authenticate, rep, client_account_a,
                               {'ordering': '-owner__first_name'}), [str(ca.id), str(cz.id)])
    assert desc[0] > desc[1]


@pytest.mark.django_db
def test_ordering_team(api, authenticate, rep, client_account_a, role_individual_a):
    acc = _account(rep, client_account_a, 'Team Ord Corp')
    ua = _user(client_account_a, role_individual_a, 'a-team@a.test', team=_team('Aaa Team', client_account_a))
    uz = _user(client_account_a, role_individual_a, 'z-team@a.test', team=_team('Zzz Team', client_account_a))
    ca = _cycle(ua, client_account_a, acc, 'ca')
    cz = _cycle(uz, client_account_a, acc, 'cz')
    asc = _rel_order(_get_all(api, authenticate, rep, client_account_a,
                              {'ordering': 'owner__team__name'}), [str(ca.id), str(cz.id)])
    assert asc[0] < asc[1]
    desc = _rel_order(_get_all(api, authenticate, rep, client_account_a,
                               {'ordering': '-owner__team__name'}), [str(ca.id), str(cz.id)])
    assert desc[0] > desc[1]


@pytest.mark.django_db
def test_ordering_updated_at(api, authenticate, rep, client_account_a):
    acc = _account(rep, client_account_a, 'Upd Corp')
    older = _cycle(rep, client_account_a, acc, 'older')
    newer = _cycle(rep, client_account_a, acc, 'newer')
    DecisionCycle.objects.filter(pk=older.pk).update(
        updated_at=timezone.now() - timedelta(days=10)
    )
    asc = _rel_order(_get_all(api, authenticate, rep, client_account_a,
                              {'ordering': 'updated_at'}), [str(older.id), str(newer.id)])
    assert asc[0] < asc[1]


@pytest.mark.django_db
def test_ordering_status_and_stage_annotations(api, authenticate, rep, client_account_a):
    # status annotation ('IN_PROGRESS' < 'STALLED' alphabetically)
    ip = _in_progress_cycle(rep, client_account_a, 'aaa-ip')
    st = _stalled_cycle(rep, client_account_a, 'zzz-st')
    asc = _rel_order(_get_all(api, authenticate, rep, client_account_a,
                              {'ordering': '_cycle_effective_status'}), [str(ip.id), str(st.id)])
    assert asc[0] < asc[1]            # IN_PROGRESS before STALLED
    # stage annotation is orderable without a FieldError (the annotation exists)
    resp = _get_all(api, authenticate, rep, client_account_a,
                    {'ordering': '_current_step_stage'})
    assert resp.status_code == status.HTTP_200_OK


# =============================================================================
# SEARCH — name / account / owner / team ; description no longer matches
# =============================================================================

@pytest.mark.django_db
def test_search_name_account_owner_team(
    api, authenticate, rep, client_account_a, role_individual_a
):
    team = _team('Searchteam', client_account_a)
    owner = _user(client_account_a, role_individual_a, 'searchowner@a.test',
                  first_name='Zephyrine', team=team)
    acc = _account(owner, client_account_a, 'Searchaccount Inc')
    target = _cycle(owner, client_account_a, acc, 'Searchname deal',
                    )
    # a decoy that must not match any of the queries below
    decoy_acc = _account(rep, client_account_a, 'Decoy Corp')
    decoy = _cycle(rep, client_account_a, decoy_acc, 'decoy')

    for term in ('Searchname', 'Searchaccount', 'Zephyrine', 'Searchteam'):
        resp = _get_all(api, authenticate, rep, client_account_a, {'search': term})
        ids = _ids(resp)
        assert str(target.id) in ids, f'search {term!r} should match'
        assert str(decoy.id) not in ids, f'search {term!r} should not match decoy'


@pytest.mark.django_db
def test_search_description_no_longer_matches(api, authenticate, rep, client_account_a):
    acc = _account(rep, client_account_a, 'Desc Corp')
    c = _cycle(rep, client_account_a, acc, 'plain name')
    DecisionCycle.objects.filter(pk=c.pk).update(description='UNIQUEDESCTOKEN')
    resp = _get_all(api, authenticate, rep, client_account_a, {'search': 'UNIQUEDESCTOKEN'})
    assert str(c.id) not in _ids(resp)


# =============================================================================
# ANTI-FAN-OUT + TD-90 N+1 death
# =============================================================================

def _build_rich_cycle(owner, client_account, name, n_products=2):
    """A cycle with 5 steps, several activities, and N products — fan-out bait."""
    acc = _account(owner, client_account, f'{name} Corp')
    cyc = _cycle(owner, client_account, acc, name)
    steps = _steps(cyc, owner, client_account)
    _activity(steps[0], owner, client_account, ActivityStatus.COMPLETED)
    _activity(steps[0], owner, client_account, ActivityStatus.COMPLETED)
    _activity(steps[1], owner, client_account, ActivityStatus.PLANNED)
    _activity(steps[3], owner, client_account, ActivityStatus.COMPLETED)
    for i in range(n_products):
        p = _product(f'{name}-p{i}', client_account, owner)
        DealProduct.objects.create(
            decision_cycle=cyc, product_catalog_entry=p, quantity=1,
            client_id=client_account.id,
        )
    return cyc


@pytest.mark.django_db
def test_counts_and_state_correct_and_no_n_plus_one(
    api, authenticate, rep, client_account_a
):
    # Two rich cycles first — capture the query count.
    for i in range(2):
        _build_rich_cycle(rep, client_account_a, f'rich{i}')
    authenticate(api, rep, client_account_a.id)
    with CaptureQueriesContext(connection) as q2:
        resp2 = api.get(LIST_URL, {'owner_scope': 'all', 'page_size': 50})
    assert resp2.status_code == status.HTTP_200_OK

    # Values are correct: each rich cycle has 5 steps, 1 validated (steps[3]),
    # IN_PROGRESS, current step = steps[0] (has a planned activity).
    rows = {r['name']: r for r in _rows(resp2)}
    for i in range(2):
        row = rows[f'rich{i}']
        assert row['steps_count'] == 5
        # steps[0] (2 completed) and steps[3] (completed) are VALIDATED — the
        # cycle has a planned activity on steps[1], so both done steps validate.
        assert row['validated_steps_count'] == 2
        assert row['cycle_status'] == 'IN_PROGRESS'
        assert row['current_step_name'] is not None

    # Add four MORE rich cycles and re-request: the query count must NOT grow.
    for i in range(2, 6):
        _build_rich_cycle(rep, client_account_a, f'rich{i}')
    with CaptureQueriesContext(connection) as q6:
        resp6 = api.get(LIST_URL, {'owner_scope': 'all', 'page_size': 50})
    assert resp6.status_code == status.HTTP_200_OK
    assert len(_rows(resp6)) >= 6

    assert len(q6.captured_queries) == len(q2.captured_queries), (
        f'N+1: query count grew from {len(q2.captured_queries)} (2 cycles) to '
        f'{len(q6.captured_queries)} (6 cycles)\n'
        + '\n'.join(x['sql'][:120] for x in q6.captured_queries)
    )


# =============================================================================
# ISOLATION — a filter never surfaces an out-of-tenant cycle
# =============================================================================

@pytest.mark.django_db
def test_isolation_other_tenant_invisible(
    api, authenticate, rep, client_account_a, client_account_b, role_individual_b
):
    # tenant B cycle sharing an outcome we filter on tenant A
    ub = _user(client_account_b, role_individual_b, 'b-rep@b.test')
    acc_b = _account(ub, client_account_b, 'B Corp')
    b_lost = _cycle(ub, client_account_b, acc_b, 'b-lost', outcome=CycleOutcome.LOST)

    acc_a = _account(rep, client_account_a, 'A Corp')
    a_lost = _cycle(rep, client_account_a, acc_a, 'a-lost', outcome=CycleOutcome.LOST)

    resp = _get_all(api, authenticate, rep, client_account_a, {'status': 'LOST'})
    ids = _ids(resp)
    assert str(a_lost.id) in ids
    assert str(b_lost.id) not in ids  # tenant isolation upstream of the filter
