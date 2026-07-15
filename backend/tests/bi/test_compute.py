# backend/tests/bi/test_compute.py
"""
Tests for the BI compute layer (app_modules/bi/compute.py).

Still "à vide": no real KPI. We exercise the compute pipeline against a
FIXTURE KPIDefinition over the Activity model, proving:
- the four pipeline stages compose (tenant -> role scope -> period -> agg),
- role scoping is the SAME as the viewsets (mine excludes other reps, but
  includes C6 account-owner records),
- the three output shapes (scalar / breakdown / timeseries) are produced by a
  single DB aggregation,
- NO N+1: the compute is bounded to one aggregate query (django_assert_num_queries).
"""

from datetime import date, timedelta

import pytest
from django.db.models import Count
from django.utils import timezone

from app_modules.activities.constants import ActivityStatus, ActivityType
from app_modules.activities.models import Activity
from app_modules.accounts.models import CompanyAccount
from app_modules.bi import compute
from app_modules.bi.registry import KPIDefinition
from app_modules.bi.types import OutputShape, Period, KPIResult
from permissions.compat import AuthContext


# =============================================================================
# Helpers / fixtures
# =============================================================================

def _ctx(user, client_account):
    return AuthContext(
        user_id=str(user.id),
        client_id=str(client_account.id),
        is_authenticated=True,
    )


def _mk_user(email, client_account, role):
    from end_users.models import User
    return User.objects.create(
        email=email, client_account=client_account, role=role, is_active=True,
    )


def _mk_account(name, owner, client_account):
    acc = CompanyAccount(company_name=name, has_buying_decision=True, account_owner=owner)
    acc.save(user=owner, client_id=client_account.id)
    return acc


def _mk_activity(owner, account, client_account, *, status=ActivityStatus.PLANNED,
                 atype=ActivityType.CALL, scheduled=None, title='act'):
    a = Activity(
        title=title,
        activity_type=atype,
        status=status,
        account=account,
        owner=owner,
        scheduled_date=scheduled or timezone.now().date(),
    )
    a.save(user=owner, client_id=client_account.id)
    return a


@pytest.fixture
def user_a(db, client_account_a, role_individual_a):
    return _mk_user('rep-a@tenant-a.test', client_account_a, role_individual_a)


@pytest.fixture
def user_a2(db, client_account_a, role_individual_a):
    return _mk_user('rep-a2@tenant-a.test', client_account_a, role_individual_a)


@pytest.fixture
def account_a(db, client_account_a, user_a):
    return _mk_account('Acct A', user_a, client_account_a)


# Fixture KPIDefinitions (no real KPI — just shapes over Activity) -----------

def _kpi_scalar():
    return KPIDefinition(
        key='fixture_activity_count',
        label='Fixture activity count',
        source=lambda: Activity.objects.all(),
        aggregation=Count('id'),
        scope_module='activities',
        period_field='scheduled_date',
        output_shape=OutputShape.SCALAR,
    )


def _kpi_breakdown():
    return KPIDefinition(
        key='fixture_activity_by_status',
        label='Fixture activity by status',
        source=lambda: Activity.objects.all(),
        aggregation=Count('id'),
        scope_module='activities',
        period_field='scheduled_date',
        output_shape=OutputShape.BREAKDOWN,
        dimension='status',
    )


def _kpi_timeseries():
    return KPIDefinition(
        key='fixture_activity_timeseries',
        label='Fixture activity timeseries',
        source=lambda: Activity.objects.all(),
        aggregation=Count('id'),
        scope_module='activities',
        period_field='scheduled_date',
        output_shape=OutputShape.TIMESERIES,
    )


# =============================================================================
# SCALAR + scope + tenant
# =============================================================================

@pytest.mark.django_db
class TestScalarScope:

    def test_mine_counts_only_my_activities(self, user_a, user_a2, account_a, client_account_a):
        _mk_activity(user_a, account_a, client_account_a)
        _mk_activity(user_a, account_a, client_account_a)
        # other rep's activity on THEIR OWN account (not user_a's) -> excluded
        account_a2 = _mk_account('Acct A2', user_a2, client_account_a)
        _mk_activity(user_a2, account_a2, client_account_a)

        res = compute.run(_kpi_scalar(), _ctx(user_a, client_account_a), scope='mine')
        assert isinstance(res, KPIResult)
        assert res.shape is OutputShape.SCALAR
        assert res.value == 2  # only user_a's (user_a2's is on their own account)

    def test_client_counts_whole_tenant(self, user_a, user_a2, account_a, client_account_a):
        _mk_activity(user_a, account_a, client_account_a)
        account_a2 = _mk_account('Acct A2', user_a2, client_account_a)
        _mk_activity(user_a2, account_a2, client_account_a)

        res = compute.run(_kpi_scalar(), _ctx(user_a, client_account_a), scope='client')
        assert res.value == 2  # both, same tenant

    def test_tenant_isolation(self, user_a, account_a, client_account_a,
                              client_account_b, role_individual_b):
        _mk_activity(user_a, account_a, client_account_a)
        # a whole separate tenant B with its own activity
        user_b = _mk_user('rep-b@tenant-b.test', client_account_b, role_individual_b)
        account_b = _mk_account('Acct B', user_b, client_account_b)
        _mk_activity(user_b, account_b, client_account_b)

        res = compute.run(_kpi_scalar(), _ctx(user_a, client_account_a), scope='client')
        assert res.value == 1  # tenant A only

    def test_mine_includes_c6_account_owner(self, user_a, user_a2, account_a, client_account_a):
        """The compute reuses apply_role_scope, so C6 flows: user_a owns the
        account; an activity created by user_a2 on it is visible under mine."""
        _mk_activity(user_a2, account_a, client_account_a, title='sdr on AE account')

        res = compute.run(_kpi_scalar(), _ctx(user_a, client_account_a), scope='mine')
        assert res.value == 1


# =============================================================================
# Period filtering
# =============================================================================

@pytest.mark.django_db
class TestPeriod:

    def test_period_window_filters(self, user_a, account_a, client_account_a):
        _mk_activity(user_a, account_a, client_account_a, scheduled=date(2026, 3, 15))
        _mk_activity(user_a, account_a, client_account_a, scheduled=date(2026, 6, 15))
        _mk_activity(user_a, account_a, client_account_a, scheduled=date(2026, 9, 15))

        period = Period(start=date(2026, 5, 1), end=date(2026, 7, 31))
        res = compute.run(_kpi_scalar(), _ctx(user_a, client_account_a),
                          scope='client', period=period)
        assert res.value == 1
        assert res.period_start == date(2026, 5, 1)
        assert res.period_end == date(2026, 7, 31)


# =============================================================================
# BREAKDOWN + TIMESERIES
# =============================================================================

@pytest.mark.django_db
class TestShapes:

    def test_breakdown_by_status(self, user_a, account_a, client_account_a):
        _mk_activity(user_a, account_a, client_account_a, status=ActivityStatus.PLANNED)
        _mk_activity(user_a, account_a, client_account_a, status=ActivityStatus.PLANNED)
        _mk_activity(user_a, account_a, client_account_a, status=ActivityStatus.COMPLETED)

        res = compute.run(_kpi_breakdown(), _ctx(user_a, client_account_a), scope='client')
        assert res.shape is OutputShape.BREAKDOWN
        assert res.value == {ActivityStatus.PLANNED: 2, ActivityStatus.COMPLETED: 1}

    def test_timeseries_by_month(self, user_a, account_a, client_account_a):
        _mk_activity(user_a, account_a, client_account_a, scheduled=date(2026, 3, 10))
        _mk_activity(user_a, account_a, client_account_a, scheduled=date(2026, 3, 20))
        _mk_activity(user_a, account_a, client_account_a, scheduled=date(2026, 5, 5))

        res = compute.run(_kpi_timeseries(), _ctx(user_a, client_account_a), scope='client')
        assert res.shape is OutputShape.TIMESERIES
        buckets = {row['period']: row['value'] for row in res.value}
        assert buckets == {date(2026, 3, 1): 2, date(2026, 5, 1): 1}
        # ordered ascending
        assert [r['period'] for r in res.value] == [date(2026, 3, 1), date(2026, 5, 1)]


# =============================================================================
# NO N+1 — the acceptance criterion
# =============================================================================

@pytest.mark.django_db
class TestNoNPlusOne:

    def test_scalar_is_single_query(self, user_a, account_a, client_account_a,
                                    django_assert_num_queries):
        for _ in range(5):
            _mk_activity(user_a, account_a, client_account_a)
        # client scope -> no team expansion; SCALAR -> exactly one aggregate query
        with django_assert_num_queries(1):
            res = compute.run(_kpi_scalar(), _ctx(user_a, client_account_a), scope='client')
            _ = res.value  # force evaluation inside the assertion

    def test_mine_scalar_is_single_query(self, user_a, account_a, client_account_a,
                                         django_assert_num_queries):
        for _ in range(5):
            _mk_activity(user_a, account_a, client_account_a)
        # mine scope builds Q from OWNERSHIP_MAP (no extra query) -> still one query
        with django_assert_num_queries(1):
            res = compute.run(_kpi_scalar(), _ctx(user_a, client_account_a), scope='mine')
            _ = res.value

    def test_breakdown_is_single_query(self, user_a, account_a, client_account_a,
                                       django_assert_num_queries):
        for _ in range(5):
            _mk_activity(user_a, account_a, client_account_a, status=ActivityStatus.PLANNED)
        for _ in range(3):
            _mk_activity(user_a, account_a, client_account_a, status=ActivityStatus.COMPLETED)
        with django_assert_num_queries(1):
            res = compute.run(_kpi_breakdown(), _ctx(user_a, client_account_a), scope='client')
            _ = dict(res.value)


# =============================================================================
# Guard: disallowed scope
# =============================================================================

@pytest.mark.django_db
class TestScopeGuard:

    def test_disallowed_scope_raises(self, user_a, client_account_a):
        kpi = KPIDefinition(
            key='fixture_client_only',
            label='client only',
            source=lambda: Activity.objects.all(),
            aggregation=Count('id'),
            scope_module='activities',
            period_field='scheduled_date',
            output_shape=OutputShape.SCALAR,
            allowed_scopes=('client',),
        )
        with pytest.raises(ValueError, match="not allowed"):
            compute.run(kpi, _ctx(user_a, client_account_a), scope='mine')
