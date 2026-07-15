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

import calendar
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
    """THE parity invariant: tile count == list count == len(rows), per window."""
    acc = _mk_account(user_a, client_account_a, 'A Corp')
    today = timezone.now().date()
    end_of_month = today.replace(day=calendar.monthrange(today.year, today.month)[1])

    _mk_act(user_a, acc, client_account_a, today - timedelta(days=3))   # overdue
    _mk_act(user_a, acc, client_account_a, today - timedelta(days=1))   # overdue
    _mk_act(user_a, acc, client_account_a, today)                       # today
    _mk_act(user_a, acc, client_account_a, today + timedelta(days=2))   # soon (week/month)
    nextm = _mk_act(user_a, acc, client_account_a, end_of_month + timedelta(days=1))  # beyond

    counts = _kpi_windows(authed_api_a)

    for window in (TodoWindow.OVERDUE, TodoWindow.TODAY, TodoWindow.THIS_WEEK, TodoWindow.THIS_MONTH):
        data = _todo_rows(authed_api_a, window=window)
        assert data['count'] == counts[window], f"count mismatch for {window}"
        assert len(data['results']) == counts[window], f"rows != count for {window}"

    # Concrete + nesting checks.
    assert counts[TodoWindow.OVERDUE] == 2
    assert counts[TodoWindow.TODAY] == 1
    assert counts[TodoWindow.THIS_MONTH] >= counts[TodoWindow.THIS_WEEK] >= counts[TodoWindow.TODAY]

    # The beyond-this-month activity is in the population but in NO forward window.
    all_rows = _todo_rows(authed_api_a)  # no window -> whole population
    assert all_rows['count'] == 5
    month_ids = {r['id'] for r in _todo_rows(authed_api_a, window=TodoWindow.THIS_MONTH)['results']}
    assert str(nextm.id) not in month_ids


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
