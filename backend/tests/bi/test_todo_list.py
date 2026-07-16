# backend/tests/bi/test_todo_list.py
"""
GET /bi/todo/ — the ROW list of the todo population, and its parity with the
todo_my_windows COUNT KPI.

THE guarantee (the reason for build_todo_population as a single source): for
every window, the tile count == the list's total count == len(rows). A "5 shown
above 4 rows" divergence is structurally impossible because both read the same
queryset and the same window predicate.

Also: window counts are correct, rows sort by effective_date, and scope isolates
(a rep sees only their own todo — cross-user AND cross-tenant).
"""

from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from app_modules.accounts.models import CompanyAccount
from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.activities.models import Activity
from app_modules.bi.definitions import load_all
from app_modules.bi.definitions.activities import TodoWindow

from tests.signals.conftest import (  # noqa: F401
    _jwt_only_no_csrf,
    api,
    authenticate,
    user_a,
    user_b,
    authed_api_a,
)


@pytest.fixture(autouse=True)
def _flush_and_load(db):
    load_all()
    cache.clear()
    yield
    cache.clear()


def _mk_account(owner, client_account, name='Corp'):
    acc = CompanyAccount(company_name=name, has_buying_decision=True, account_owner=owner)
    acc.save(user=owner, client_id=client_account.id)
    return acc


def _mk_act(owner, account, client_account, due):
    a = Activity(
        title=f'todo {due}', activity_type=ActivityType.CALL,
        status=ActivityStatus.PLANNED, account=account, owner=owner, due_date=due,
    )
    a.save(user=owner, client_id=client_account.id)
    return a


def _kpi_windows(client, scope='mine'):
    resp = client.get(f'/bi/kpi/todo_my_windows/?scope={scope}')
    assert resp.status_code == 200
    return resp.data['data']['value']


def _todo_rows(client, window=None, scope='mine'):
    url = f'/bi/todo/?scope={scope}'
    if window:
        url += f'&window={window}'
    resp = client.get(url)
    assert resp.status_code == 200
    return resp.data['data']


@pytest.mark.django_db
def test_count_equals_rows_per_window_parity(authed_api_a, user_a, client_account_a):
    """THE parity invariant: tile count == list count == len(rows), per window.
    Rolling windows: today ⊂ next_7_days ([today, +7]) ⊂ next_4_weeks ([today, +28])."""
    acc = _mk_account(user_a, client_account_a, 'A Corp')
    today = timezone.now().date()

    _mk_act(user_a, acc, client_account_a, today - timedelta(days=3))   # overdue
    _mk_act(user_a, acc, client_account_a, today - timedelta(days=1))   # overdue
    _mk_act(user_a, acc, client_account_a, today)                       # today
    _mk_act(user_a, acc, client_account_a, today + timedelta(days=2))   # next_7_days (& next_4_weeks)
    _mk_act(user_a, acc, client_account_a, today + timedelta(days=14))  # next_4_weeks only
    beyond = _mk_act(user_a, acc, client_account_a, today + timedelta(days=40))  # beyond every window

    counts = _kpi_windows(authed_api_a)

    for window in (TodoWindow.OVERDUE, TodoWindow.TODAY, TodoWindow.NEXT_7_DAYS, TodoWindow.NEXT_4_WEEKS):
        data = _todo_rows(authed_api_a, window=window)
        assert data['count'] == counts[window], f"count mismatch for {window}"
        assert len(data['results']) == counts[window], f"rows != count for {window}"

    # Concrete + nesting checks.
    assert counts[TodoWindow.OVERDUE] == 2
    assert counts[TodoWindow.TODAY] == 1
    assert counts[TodoWindow.NEXT_7_DAYS] == 2       # today + the +2d row
    assert counts[TodoWindow.NEXT_4_WEEKS] == 3      # + the +14d row
    assert counts[TodoWindow.NEXT_4_WEEKS] >= counts[TodoWindow.NEXT_7_DAYS] >= counts[TodoWindow.TODAY]

    # The beyond-horizon activity is in the population but in NO forward window.
    all_rows = _todo_rows(authed_api_a)  # no window -> whole population
    assert all_rows['count'] == 6
    month_ids = {r['id'] for r in _todo_rows(authed_api_a, window=TodoWindow.NEXT_4_WEEKS)['results']}
    assert str(beyond.id) not in month_ids


@pytest.mark.django_db
def test_rows_sorted_by_effective_date(authed_api_a, user_a, client_account_a):
    acc = _mk_account(user_a, client_account_a, 'A Corp')
    today = timezone.now().date()
    _mk_act(user_a, acc, client_account_a, today)                     # later
    earliest = _mk_act(user_a, acc, client_account_a, today - timedelta(days=5))  # earliest

    rows = _todo_rows(authed_api_a)['results']
    assert rows[0]['id'] == str(earliest.id)  # ascending by effective_date


@pytest.mark.django_db
def test_rows_carry_nav_ids(authed_api_a, user_a, client_account_a):
    acc = _mk_account(user_a, client_account_a, 'A Corp')
    _mk_act(user_a, acc, client_account_a, timezone.now().date())
    row = _todo_rows(authed_api_a, window=TodoWindow.TODAY)['results'][0]
    assert row['account']['id'] == str(acc.id)          # -> /accounts/{id}
    assert 'decision_cycle' in row and 'campaign' in row  # -> DC / campaign links
    assert row['effective_date'] is not None


@pytest.mark.django_db
def test_scope_isolates_cross_user(authed_api_a, user_a, user_b, client_account_a):
    """A rep's todo excludes another rep's activity (mine scope)."""
    from end_users.models import User
    other = User.objects.create(email='other@a.test', client_account=client_account_a,
                                role=user_a.role, is_active=True)
    acc_a = _mk_account(user_a, client_account_a, 'A Corp')
    acc_o = _mk_account(other, client_account_a, 'Other Corp')
    mine = _mk_act(user_a, acc_a, client_account_a, timezone.now().date())
    _mk_act(other, acc_o, client_account_a, timezone.now().date())  # not mine

    rows = _todo_rows(authed_api_a)['results']
    ids = {r['id'] for r in rows}
    assert str(mine.id) in ids
    assert len(ids) == 1  # only the caller's own


@pytest.mark.django_db
def test_scope_isolates_cross_tenant(
    authed_api_a, user_a, client_account_a, user_b, client_account_b
):
    acc_a = _mk_account(user_a, client_account_a, 'A Corp')
    acc_b = _mk_account(user_b, client_account_b, 'B Corp')
    _mk_act(user_a, acc_a, client_account_a, timezone.now().date())
    _mk_act(user_b, acc_b, client_account_b, timezone.now().date())  # other tenant

    rows = _todo_rows(authed_api_a)['results']
    assert len(rows) == 1  # tenant A only


def _mk_titled(owner, account, client_account, title, due):
    a = Activity(title=title, activity_type=ActivityType.CALL,
                 status=ActivityStatus.PLANNED, account=account, owner=owner, due_date=due)
    a.save(user=owner, client_id=client_account.id)
    return a


@pytest.mark.django_db
def test_search_filters_by_title_and_account(authed_api_a, user_a, client_account_a):
    """Server-side search matches the activity title OR the account company name."""
    acme = _mk_account(user_a, client_account_a, 'Acme Industries')
    globex = _mk_account(user_a, client_account_a, 'Globex')
    today = timezone.now().date()
    by_title = _mk_titled(user_a, globex, client_account_a, 'Call the Widget team', today)
    by_account = _mk_titled(user_a, acme, client_account_a, 'Prep deck', today)
    _mk_titled(user_a, globex, client_account_a, 'Unrelated', today)  # matches neither

    # Title match.
    resp = authed_api_a.get('/bi/todo/?scope=mine&search=widget')
    assert resp.status_code == 200
    assert {r['id'] for r in resp.data['data']['results']} == {str(by_title.id)}

    # Account-name match.
    resp = authed_api_a.get('/bi/todo/?scope=mine&search=acme')
    assert {r['id'] for r in resp.data['data']['results']} == {str(by_account.id)}


@pytest.mark.django_db
def test_search_filters_by_context_name(authed_api_a, user_a, client_account_a):
    """Search also matches the row's CONTEXT name — the decision cycle OR the
    campaign (the 'Name' column) — on both the rep and manager tables."""
    from app_modules.campaigns.models.campaign import Campaign
    from app_modules.decision_cycles.models import DecisionCycle

    acc = _mk_account(user_a, client_account_a, 'Neutral Corp')
    today = timezone.now().date()

    dc = DecisionCycle(account=acc, owner=user_a, name='Zephyr Renewal')
    dc.save(user=user_a, client_id=client_account_a.id)
    a_dc = Activity(title='step call', activity_type=ActivityType.CALL,
                    status=ActivityStatus.PLANNED, account=acc, owner=user_a,
                    decision_cycle=dc, due_date=today)
    a_dc.save(user=user_a, client_id=client_account_a.id)

    camp = Campaign(name='Nimbus Outbound', campaign_type='OUTBOUND', owner=user_a,
                    planned_start_date=today, planned_end_date=today + timedelta(days=30))
    camp.save(user=user_a, client_id=client_account_a.id)
    a_camp = Activity(title='seq email', activity_type=ActivityType.CALL,
                      status=ActivityStatus.PLANNED, account=acc, owner=user_a,
                      campaign=camp, due_date=today)
    a_camp.save(user=user_a, client_id=client_account_a.id)

    _mk_titled(user_a, acc, client_account_a, 'Unrelated', today)  # neither DC nor campaign

    # Decision-cycle name.
    resp = authed_api_a.get('/bi/todo/?scope=mine&search=zephyr')
    assert {r['id'] for r in resp.data['data']['results']} == {str(a_dc.id)}
    # Campaign name.
    resp = authed_api_a.get('/bi/todo/?scope=mine&search=nimbus')
    assert {r['id'] for r in resp.data['data']['results']} == {str(a_camp.id)}


@pytest.mark.django_db
def test_rep_search_does_not_match_team_name(authed_api_a, user_a, client_account_a):
    """The rep table has NO Team column, so team name is NOT searchable there
    (include_team defaults to False). Proves the flag gating, not just the add."""
    from end_users.models import Team

    user_a.team = Team.objects.create(name='RepSquad', client_account=client_account_a)
    user_a.save(update_fields=['team'])
    acc = _mk_account(user_a, client_account_a, 'Plain Corp')
    today = timezone.now().date()
    _mk_titled(user_a, acc, client_account_a, 'A task', today)

    # 'repsquad' matches only the team name — which the rep search must ignore.
    resp = authed_api_a.get('/bi/todo/?scope=mine&search=repsquad')
    assert resp.status_code == 200
    assert resp.data['data']['results'] == []


@pytest.mark.django_db
def test_ordering_by_account_name_asc_and_desc(authed_api_a, user_a, client_account_a):
    alpha = _mk_account(user_a, client_account_a, 'Alpha Co')
    zeta = _mk_account(user_a, client_account_a, 'Zeta Co')
    today = timezone.now().date()
    a = _mk_titled(user_a, alpha, client_account_a, 'a', today)
    z = _mk_titled(user_a, zeta, client_account_a, 'z', today)

    asc = authed_api_a.get('/bi/todo/?scope=mine&ordering=account__company_name')
    assert [r['id'] for r in asc.data['data']['results']] == [str(a.id), str(z.id)]

    desc = authed_api_a.get('/bi/todo/?scope=mine&ordering=-account__company_name')
    assert [r['id'] for r in desc.data['data']['results']] == [str(z.id), str(a.id)]


@pytest.mark.django_db
def test_ordering_unknown_field_rejected(authed_api_a, user_a, client_account_a):
    """Strict whitelist: a real-but-unlisted field (status) is a 400, not a silent
    fallback."""
    acc = _mk_account(user_a, client_account_a, 'A Corp')
    _mk_act(user_a, acc, client_account_a, timezone.now().date())
    resp = authed_api_a.get('/bi/todo/?scope=mine&ordering=status')
    assert resp.status_code == 400


@pytest.mark.django_db
def test_ordering_by_title(authed_api_a, user_a, client_account_a):
    acc = _mk_account(user_a, client_account_a, 'A Corp')
    today = timezone.now().date()
    apple = _mk_titled(user_a, acc, client_account_a, 'Apple', today)
    zebra = _mk_titled(user_a, acc, client_account_a, 'Zebra', today)
    asc = authed_api_a.get('/bi/todo/?scope=mine&ordering=title')
    assert [r['id'] for r in asc.data['data']['results']] == [str(apple.id), str(zebra.id)]


@pytest.mark.django_db
def test_ordering_by_activity_type_is_reversible(authed_api_a, user_a, client_account_a):
    """Order by activity_type asc then desc — robust check without hardcoding the
    enum values: desc is the reverse of asc."""
    acc = _mk_account(user_a, client_account_a, 'A Corp')
    today = timezone.now().date()
    a = Activity(title='a', activity_type=ActivityType.CALL, status=ActivityStatus.PLANNED,
                 account=acc, owner=user_a, due_date=today)
    a.save(user=user_a, client_id=client_account_a.id)
    b = Activity(title='b', activity_type=ActivityType.MEETING, status=ActivityStatus.PLANNED,
                 account=acc, owner=user_a, due_date=today)
    b.save(user=user_a, client_id=client_account_a.id)

    asc = [r['id'] for r in authed_api_a.get('/bi/todo/?scope=mine&ordering=activity_type').data['data']['results']]
    desc = [r['id'] for r in authed_api_a.get('/bi/todo/?scope=mine&ordering=-activity_type').data['data']['results']]
    assert asc == list(reversed(desc))
    assert set(asc) == {str(a.id), str(b.id)}


@pytest.mark.django_db
def test_ordering_by_context_name_and_kind(authed_api_a, user_a, client_account_a):
    """Context sort: name = COALESCE(dc.name, campaign.name); kind = which one.
    An activity has a decision cycle OR a campaign."""
    from app_modules.decision_cycles.models import DecisionCycle
    from app_modules.campaigns.models import Campaign

    acc = _mk_account(user_a, client_account_a, 'A Corp')
    today = timezone.now().date()

    dc = DecisionCycle(account=acc, owner=user_a, name='Zeta Cycle', is_active=True)
    dc.save(user=user_a, client_id=client_account_a.id)
    camp = Campaign(name='Alpha Camp', campaign_type='OUTBOUND', owner=user_a,
                    planned_start_date=today, planned_end_date=today + timedelta(days=30))
    camp.save(user=user_a, client_id=client_account_a.id)

    on_dc = Activity(title='c1', activity_type=ActivityType.CALL, status=ActivityStatus.PLANNED,
                     account=acc, owner=user_a, due_date=today, decision_cycle=dc)
    on_dc.save(user=user_a, client_id=client_account_a.id)
    on_camp = Activity(title='c2', activity_type=ActivityType.CALL, status=ActivityStatus.PLANNED,
                       account=acc, owner=user_a, due_date=today, campaign=camp)
    on_camp.save(user=user_a, client_id=client_account_a.id)

    # By name: 'Alpha Camp' < 'Zeta Cycle' -> campaign row first.
    by_name = authed_api_a.get('/bi/todo/?scope=mine&ordering=context_name')
    assert [r['id'] for r in by_name.data['data']['results']] == [str(on_camp.id), str(on_dc.id)]

    # By kind: 'campaign' < 'decision_cycle' -> campaign row first.
    by_kind = authed_api_a.get('/bi/todo/?scope=mine&ordering=context_kind')
    assert [r['id'] for r in by_kind.data['data']['results']] == [str(on_camp.id), str(on_dc.id)]


@pytest.mark.django_db
def test_default_ordering_unchanged_is_effective_date_asc(authed_api_a, user_a, client_account_a):
    """No ordering param -> overdue first (effective_date asc), unchanged framing."""
    acc = _mk_account(user_a, client_account_a, 'A Corp')
    today = timezone.now().date()
    later = _mk_titled(user_a, acc, client_account_a, 'later', today)
    earlier = _mk_titled(user_a, acc, client_account_a, 'earlier', today - timedelta(days=4))
    rows = _todo_rows(authed_api_a)['results']
    assert [r['id'] for r in rows] == [str(earlier.id), str(later.id)]
