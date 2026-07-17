# backend/tests/bi/test_territory_coverage_core.py
"""
The SHARED territory-coverage core (territories.services.coverage).

This is the ONE definition of a territory's (numerator, denominator) — consumed
by the live per-territory KPI (rep Home) and, next, by the manager-aggregate
snapshot. These tests lock two things:

  1. the core returns EXACTLY what the per-territory KPI reports for the same
     territory + period (they can't diverge — the whole point of extracting it);
  2. the core is query-bounded to 2 COUNTs (no per-account N+1), independent of
     the number of accounts — the property the snapshot relies on to bound its
     refresh cost.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from app_modules.accounts.models import CompanyAccount, AccountClassification
from app_modules.activities.constants import ActivityStatus, ActivityType, ActivityOutcome
from app_modules.activities.models import Activity
from app_modules.territories.models import Territory
from app_modules.territories.services.coverage import compute_territory_coverage_counts
from app_modules.bi import registry
from app_modules.bi.cache import cached_run
from app_modules.bi.definitions import load_all
from app_modules.bi.definitions.territory import territory_coverage
from app_modules.bi.types import Period
from permissions.compat import AuthContext


TODAY = timezone.now().date()
PERIOD = Period(start=TODAY - timedelta(days=30), end=TODAY)


def _ctx(user, ca):
    return AuthContext(user_id=str(user.id), client_id=str(ca.id), is_authenticated=True)


def _mk_user(email, ca, role):
    from end_users.models import User
    return User.objects.create(email=email, client_account=ca, role=role, is_active=True)


def _mk_account(name, owner, ca, classification=AccountClassification.SMB):
    acc = CompanyAccount(company_name=name, has_buying_decision=True,
                         account_owner=owner, classification=classification)
    acc.save(user=owner, client_id=ca.id)
    return acc


def _mk_territory(owner, ca, filter_definition):
    t = Territory(name='Core-T', type='ACCOUNT', owner=owner,
                  filter_definition=filter_definition)
    t.save(user=owner, client_id=ca.id)
    return t


def _touch(account, owner, ca, when=None, outcome=ActivityOutcome.SUCCESSFUL):
    a = Activity(title='t', activity_type=ActivityType.CALL,
                 status=ActivityStatus.COMPLETED, outcome=outcome,
                 account=account, owner=owner, scheduled_date=when or TODAY)
    a.save(user=owner, client_id=ca.id)
    return a


@pytest.fixture
def kpi(db):
    load_all()
    yield territory_coverage
    registry.clear()


@pytest.fixture
def user_a(db, client_account_a, role_individual_a):
    return _mk_user('core-a@a.test', client_account_a, role_individual_a)


@pytest.mark.django_db
def test_core_matches_the_kpi_meta_exactly(kpi, user_a, client_account_a):
    """The core's (num, den) IS the KPI's reported (num, den) — same territory."""
    terr = _mk_territory(user_a, client_account_a, {'classification': 'SMB'})
    a1 = _mk_account('SMB1', user_a, client_account_a)
    a2 = _mk_account('SMB2', user_a, client_account_a)
    _mk_account('SMB3', user_a, client_account_a)
    _mk_account('SMB4', user_a, client_account_a)
    _mk_account('ENT', user_a, client_account_a, classification=AccountClassification.ENTERPRISE)
    _touch(a1, user_a, client_account_a)
    _touch(a2, user_a, client_account_a)

    num, den = compute_territory_coverage_counts(terr, client_account_a.id, PERIOD)
    assert (num, den) == (2, 4)  # 2 SMB touched of 4 SMB (ENT excluded)

    res = cached_run(kpi, _ctx(user_a, client_account_a), scope='mine',
                     period=PERIOD, params={'territory_id': str(terr.id)})
    # The two agree by construction — this is what "can't diverge" means.
    assert (res.meta['numerator'], res.meta['denominator']) == (num, den)


@pytest.mark.django_db
def test_core_honours_the_period_window(kpi, user_a, client_account_a):
    """A response outside the period does not count toward the numerator."""
    terr = _mk_territory(user_a, client_account_a, {'classification': 'SMB'})
    a1 = _mk_account('SMB1', user_a, client_account_a)
    a2 = _mk_account('SMB2', user_a, client_account_a)
    _touch(a1, user_a, client_account_a, when=TODAY)                        # in window
    _touch(a2, user_a, client_account_a, when=TODAY - timedelta(days=400))  # out of window

    num, den = compute_territory_coverage_counts(terr, client_account_a.id, PERIOD)
    assert (num, den) == (1, 2)


@pytest.mark.django_db
def test_core_is_two_queries_regardless_of_account_count(kpi, user_a, client_account_a,
                                                         django_assert_num_queries):
    """Exactly 2 COUNTs (denominator + numerator), no per-account N+1 — the
    bound the snapshot refresh will lean on."""
    terr = _mk_territory(user_a, client_account_a, {'classification': 'SMB'})
    for i in range(8):  # many accounts -> would explode if per-account
        acc = _mk_account(f'SMB{i}', user_a, client_account_a)
        _touch(acc, user_a, client_account_a)

    with django_assert_num_queries(2):
        compute_territory_coverage_counts(terr, client_account_a.id, PERIOD)
