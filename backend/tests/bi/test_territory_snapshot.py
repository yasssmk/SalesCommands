# backend/tests/bi/test_territory_snapshot.py
"""
The lazy coverage-snapshot refresh (territories.services.snapshot).

Proves the read-refresh contract the manager aggregate relies on:
  - a stale snapshot is recomputed (columns move, computed_at stamped);
  - a FRESH one is NOT recomputed (the TTL earns its keep);
  - a period_key mismatch forces a recompute even when computed_at is fresh
    (the FY25-read-in-FY26 bug is impossible by construction);
  - SKIP LOCKED skips a row another transaction holds (concurrent readers split
    the work, never block or double-compute);
  - the per-read budget caps the refresh (NULL/oldest first, the rest left
    intact, the cap logged);
  - the query cost is linear and bounded (1 locked SELECT + 2 COUNTs/row + 1
    bulk UPDATE), no per-account N+1.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from app_modules.accounts.models import CompanyAccount, AccountClassification
from app_modules.activities.constants import ActivityStatus, ActivityType, ActivityOutcome
from app_modules.activities.models import Activity
from app_modules.territories.models import Territory
from app_modules.territories.services.snapshot import (
    SNAPSHOT_REFRESH_BUDGET,
    period_key_for,
    refresh_stale_snapshots,
)
from app_modules.bi.types import Period


TODAY = timezone.now().date()
PERIOD = Period(start=TODAY - timedelta(days=30), end=TODAY)
PERIOD_KEY = period_key_for(PERIOD)
NOW = timezone.now()


def _mk_user(email, ca, role):
    from end_users.models import User
    return User.objects.create(email=email, client_account=ca, role=role, is_active=True)


def _mk_account(name, owner, ca, classification=AccountClassification.SMB):
    acc = CompanyAccount(company_name=name, has_buying_decision=True,
                         account_owner=owner, classification=classification)
    acc.save(user=owner, client_id=ca.id)
    return acc


_seq = 0


def _mk_territory(owner, ca, filter_definition=None):
    global _seq
    _seq += 1
    t = Territory(name=f'Snap-{_seq}', type='ACCOUNT', owner=owner,
                  filter_definition=filter_definition or {'classification': 'SMB'})
    t.save(user=owner, client_id=ca.id)
    return t


def _touch(account, owner, ca, when=None):
    a = Activity(title='t', activity_type=ActivityType.CALL,
                 status=ActivityStatus.COMPLETED, outcome=ActivityOutcome.SUCCESSFUL,
                 account=account, owner=owner, scheduled_date=when or TODAY)
    a.save(user=owner, client_id=ca.id)
    return a


def _set_snapshot(terr, *, num, den, period_key, computed_at):
    """Write a snapshot directly (bypasses save()) to stage stale/fresh state."""
    Territory.objects.filter(id=terr.id).update(
        coverage_numerator=num, coverage_denominator=den,
        coverage_period_key=period_key, coverage_computed_at=computed_at,
    )


@pytest.fixture
def user_a(db, client_account_a, role_individual_a):
    return _mk_user('snap-a@a.test', client_account_a, role_individual_a)


def _all_terr():
    return Territory.objects.all()


@pytest.mark.django_db
def test_stale_never_computed_is_refreshed(user_a, client_account_a):
    terr = _mk_territory(user_a, client_account_a)
    a1 = _mk_account('SMB1', user_a, client_account_a)
    _mk_account('SMB2', user_a, client_account_a)
    _touch(a1, user_a, client_account_a)  # 1 of 2 SMB touched

    n = refresh_stale_snapshots(_all_terr(), client_id=client_account_a.id,
                                period=PERIOD, now=NOW)
    assert n == 1
    terr.refresh_from_db()
    assert (terr.coverage_numerator, terr.coverage_denominator) == (1, 2)
    assert terr.coverage_period_key == PERIOD_KEY
    assert terr.coverage_computed_at == NOW


@pytest.mark.django_db
def test_fresh_snapshot_is_not_recomputed(user_a, client_account_a):
    """A snapshot within the TTL is left untouched — even if reality changed.
    The stored counts stay 'wrong' on purpose: proof the TTL is honoured."""
    terr = _mk_territory(user_a, client_account_a)
    a1 = _mk_account('SMB1', user_a, client_account_a)
    _mk_account('SMB2', user_a, client_account_a)
    _touch(a1, user_a, client_account_a)  # reality = 1/2

    fresh_at = NOW - timedelta(hours=1)   # within the 2h TTL
    _set_snapshot(terr, num=99, den=99, period_key=PERIOD_KEY, computed_at=fresh_at)

    n = refresh_stale_snapshots(_all_terr(), client_id=client_account_a.id,
                                period=PERIOD, now=NOW)
    assert n == 0
    terr.refresh_from_db()
    # untouched: still the stale 99/99, computed_at not moved. If the TTL were
    # ignored these would be 1/2 at NOW.
    assert (terr.coverage_numerator, terr.coverage_denominator) == (99, 99)
    assert terr.coverage_computed_at == fresh_at


@pytest.mark.django_db
def test_period_key_mismatch_forces_recompute_even_when_fresh(user_a, client_account_a):
    terr = _mk_territory(user_a, client_account_a)
    a1 = _mk_account('SMB1', user_a, client_account_a)
    _mk_account('SMB2', user_a, client_account_a)
    _touch(a1, user_a, client_account_a)  # reality = 1/2 for PERIOD

    # Fresh by TTL (1 min old) but computed for a DIFFERENT period.
    _set_snapshot(terr, num=99, den=99, period_key='FY-OLD',
                  computed_at=NOW - timedelta(minutes=1))

    n = refresh_stale_snapshots(_all_terr(), client_id=client_account_a.id,
                                period=PERIOD, now=NOW)
    assert n == 1
    terr.refresh_from_db()
    assert (terr.coverage_numerator, terr.coverage_denominator) == (1, 2)
    assert terr.coverage_period_key == PERIOD_KEY
    assert terr.coverage_computed_at == NOW


@pytest.mark.django_db
def test_budget_caps_refresh_null_and_oldest_first_rest_intact(user_a, client_account_a, caplog):
    """N+1 stale, budget K -> K refreshed (NULL first, then oldest), the rest
    left intact, and the cap logged."""
    # t_null: never computed. t_old: 10h stale. t_recent: 3h stale (still > 2h).
    t_null = _mk_territory(user_a, client_account_a)
    t_old = _mk_territory(user_a, client_account_a)
    t_recent = _mk_territory(user_a, client_account_a)
    _set_snapshot(t_old, num=0, den=0, period_key=PERIOD_KEY, computed_at=NOW - timedelta(hours=10))
    recent_at = NOW - timedelta(hours=3)
    _set_snapshot(t_recent, num=0, den=0, period_key=PERIOD_KEY, computed_at=recent_at)

    import logging
    with caplog.at_level(logging.INFO):
        n = refresh_stale_snapshots(_all_terr(), client_id=client_account_a.id,
                                    period=PERIOD, now=NOW, budget=2)
    assert n == 2

    for t in (t_null, t_old, t_recent):
        t.refresh_from_db()
    # NULL first, then the oldest computed -> t_null and t_old refreshed.
    assert t_null.coverage_computed_at == NOW
    assert t_old.coverage_computed_at == NOW
    # t_recent left intact (budget exhausted) — its old snapshot is preserved.
    assert t_recent.coverage_computed_at == recent_at
    # cap logged, never silently dropped.
    assert any('budget cap' in r.message for r in caplog.records)


@pytest.mark.django_db
def test_query_bounded_linear_in_budget(user_a, client_account_a, django_assert_num_queries):
    """K stale territories, budget K: 1 locked SELECT + 2 COUNTs/row + 1 bulk
    UPDATE (+ savepoint enter/exit) — linear in K, no per-account N+1."""
    K = 3
    for i in range(K):
        t = _mk_territory(user_a, client_account_a)
        for j in range(4):  # accounts per territory — must NOT add queries
            acc = _mk_account(f'A{i}-{j}', user_a, client_account_a)
            _touch(acc, user_a, client_account_a)

    # 1 (locked select) + K*2 (den+num counts) + 1 (bulk_update) + 2 (savepoint
    # enter/release from the inner atomic) = 2K + 4.
    with django_assert_num_queries(2 * K + 4):
        refresh_stale_snapshots(_all_terr(), client_id=client_account_a.id,
                                period=PERIOD, now=NOW, budget=K)


@pytest.mark.django_db(transaction=True)
def test_skip_locked_skips_a_row_held_by_another_transaction(client_account_a, role_individual_a):
    """A row locked FOR UPDATE by a concurrent transaction is SKIPPED: the free
    row is refreshed, the locked one is left stale, and only 1 is refreshed."""
    import threading
    from django.db import connections, transaction

    user = _mk_user('snap-lock@a.test', client_account_a, role_individual_a)
    t_locked = _mk_territory(user, client_account_a)
    t_free = _mk_territory(user, client_account_a)

    locked_ready = threading.Event()
    release = threading.Event()

    def hold_lock():
        try:
            with transaction.atomic():
                # take a real row lock on t_locked and hold it
                list(Territory.objects.filter(id=t_locked.id).select_for_update())
                locked_ready.set()
                release.wait(timeout=10)
        finally:
            connections['default'].close()

    thread = threading.Thread(target=hold_lock)
    thread.start()
    try:
        assert locked_ready.wait(timeout=10), 'lock thread did not acquire the lock'
        n = refresh_stale_snapshots(_all_terr(), client_id=client_account_a.id,
                                    period=PERIOD, now=NOW)
    finally:
        release.set()
        thread.join(timeout=10)

    assert n == 1  # only the free row
    t_free.refresh_from_db()
    t_locked.refresh_from_db()
    assert t_free.coverage_computed_at == NOW      # refreshed
    assert t_locked.coverage_computed_at is None   # skipped, still stale
    # No manual cleanup: transaction=True flushes all tables after the test.
