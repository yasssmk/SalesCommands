# backend/tests/signals/test_techstack_usage_departments.py
"""
Tech scope (usage) — sub-step 1/3: the multi-department usage relation.

Proves the `usage_departments` M2M added to TechStackSignal end to end:

  * MODEL: a signal can carry 0, 1, or SEVERAL usage departments
    ("Sales AND Marketing on HubSpot" is legitimate, multi-department).
  * SERIALIZER (List + Detail via the real API): usage_departments is
    exposed as a list of compact {id, name} payloads — [] when none,
    one entry per linked department otherwise. The single-FK
    usage_department stays exposed and independent.
  * N+1 SAFETY: the list endpoint issues a constant number of queries
    regardless of how many departments each signal carries — the
    ViewSet's prefetch_related('usage_departments') loads them in one
    extra query for the whole page.

The M2M is populated directly here (the model layer); the extraction
that fills it from a transcript lands in sub-step 2 and is out of scope.
"""

import pytest
from django.urls import reverse
from rest_framework import status

from app_modules.signals.constants import SignalSource
from app_modules.signals.models import TechStackSignal


pytestmark = pytest.mark.django_db(transaction=True)


# =============================================================================
# FIXTURES — standard departments (global controlled vocabulary)
# =============================================================================

@pytest.fixture
def dept_sales(db):
    from app_modules.core_modules.models import StandardDepartment
    d, _ = StandardDepartment.objects.get_or_create(name='Sales')
    return d


@pytest.fixture
def dept_marketing(db):
    from app_modules.core_modules.models import StandardDepartment
    d, _ = StandardDepartment.objects.get_or_create(name='Marketing')
    return d


# =============================================================================
# HELPERS
# =============================================================================

def _make_signal(account, activity, user, tech_name='HubSpot'):
    """A minimal LLM-extracted TechStack row, no departments attached yet."""
    sig = TechStackSignal(
        account=account,
        source_activity=activity,
        tech_name=tech_name,
        source=SignalSource.LLM_EXTRACTED,
        source_quote='the whole team lives in HubSpot',
    )
    sig.save(user=user, client_id=account.client_id)
    return sig


def _url_list():
    return reverse('module_signals:tech-stack-list')


def _url_detail(pk):
    return reverse('module_signals:tech-stack-detail', kwargs={'pk': pk})


def _results(response):
    body = response.json()
    results = body.get('results') or body.get('data', {}).get('results') or body
    if isinstance(results, dict):
        results = results.get('results', results)
    return results


def _row(response, signal_id):
    return next(r for r in _results(response) if r['id'] == str(signal_id))


# =============================================================================
# MODEL — 0 / 1 / many departments
# =============================================================================

class TestModelMultiDepartment:

    def test_signal_starts_with_no_usage_departments(
        self, account, activity, user_a,
    ):
        sig = _make_signal(account, activity, user_a)
        assert list(sig.usage_departments.all()) == []

    def test_signal_can_carry_a_single_department(
        self, account, activity, user_a, dept_marketing,
    ):
        sig = _make_signal(account, activity, user_a)
        sig.usage_departments.add(dept_marketing)
        assert list(sig.usage_departments.all()) == [dept_marketing]

    def test_signal_can_carry_several_departments(
        self, account, activity, user_a, dept_sales, dept_marketing,
    ):
        """The core product requirement: one tool, multiple using departments."""
        sig = _make_signal(account, activity, user_a)
        sig.usage_departments.add(dept_sales, dept_marketing)

        names = set(sig.usage_departments.values_list('name', flat=True))
        assert names == {'Sales', 'Marketing'}

    def test_reverse_relation_lists_signals_using_a_department(
        self, account, activity, user_a, dept_marketing,
    ):
        sig = _make_signal(account, activity, user_a)
        sig.usage_departments.add(dept_marketing)

        assert sig in dept_marketing.tech_stack_signals_used_by.all()


# =============================================================================
# SERIALIZER — List + Detail expose the compact list
# =============================================================================

class TestSerializerExposesUsageDepartments:

    def test_list_exposes_empty_list_when_none(
        self, authed_api_a, account, activity, user_a,
    ):
        sig = _make_signal(account, activity, user_a)

        resp = authed_api_a.get(
            _url_list(), {'source_activity': str(activity.id)},
        )
        assert resp.status_code == status.HTTP_200_OK
        row = _row(resp, sig.id)
        assert row['usage_departments'] == []

    def test_list_exposes_all_departments_multi(
        self, authed_api_a, account, activity, user_a, dept_sales, dept_marketing,
    ):
        sig = _make_signal(account, activity, user_a)
        sig.usage_departments.add(dept_sales, dept_marketing)

        resp = authed_api_a.get(
            _url_list(), {'source_activity': str(activity.id)},
        )
        assert resp.status_code == status.HTTP_200_OK
        row = _row(resp, sig.id)

        expected = {
            (str(dept_sales.id), dept_sales.get_name_display()),
            (str(dept_marketing.id), dept_marketing.get_name_display()),
        }
        got = {(d['id'], d['name']) for d in row['usage_departments']}
        assert got == expected

    def test_detail_exposes_all_departments_multi(
        self, authed_api_a, account, activity, user_a, dept_sales, dept_marketing,
    ):
        sig = _make_signal(account, activity, user_a)
        sig.usage_departments.add(dept_sales, dept_marketing)

        resp = authed_api_a.get(_url_detail(sig.id))
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        payload = body.get('data', body)

        got = {(d['id'], d['name']) for d in payload['usage_departments']}
        expected = {
            (str(dept_sales.id), dept_sales.get_name_display()),
            (str(dept_marketing.id), dept_marketing.get_name_display()),
        }
        assert got == expected

    def test_single_fk_usage_department_is_independent(
        self, authed_api_a, account, activity, user_a, dept_sales, dept_marketing,
    ):
        """
        The M2M (who uses) does not disturb the legacy single-FK
        usage_department: a signal with only usage_departments set still
        reports usage_department = null.
        """
        sig = _make_signal(account, activity, user_a)
        sig.usage_departments.add(dept_sales, dept_marketing)

        resp = authed_api_a.get(
            _url_list(), {'source_activity': str(activity.id)},
        )
        row = _row(resp, sig.id)
        assert row['usage_department'] is None
        assert len(row['usage_departments']) == 2


# =============================================================================
# N+1 SAFETY — constant query count regardless of department fan-out
# =============================================================================

class TestUsageDepartmentsAreNPlusOneSafe:

    def test_query_count_is_constant_across_department_fanout(
        self, authed_api_a, account, activity, user_a,
        dept_sales, dept_marketing, django_assert_num_queries,
    ):
        """
        Two list scenarios over the same number of signals:
          A. every signal carries ONE department;
          B. every signal carries TWO departments.

        With prefetch_related('usage_departments') the endpoint fires the
        SAME number of queries in both — the M2M is loaded in a single
        extra query for the whole page, not once per signal-department.
        A missing prefetch would make B strictly heavier than A.
        """
        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        def _seed(n, depts):
            for i in range(n):
                s = _make_signal(account, activity, user_a, tech_name=f'Tool{i}')
                s.usage_departments.add(*depts)

        def _count_list_queries():
            with CaptureQueriesContext(connection) as ctx:
                resp = authed_api_a.get(
                    _url_list(), {'source_activity': str(activity.id)},
                )
                assert resp.status_code == status.HTTP_200_OK
            return len(ctx.captured_queries)

        # Scenario A: 3 signals × 1 department.
        _seed(3, [dept_marketing])
        count_single = _count_list_queries()

        # Scenario B: 3 more signals × 2 departments (6 signals total now,
        # the newer ones each carrying two departments).
        _seed(3, [dept_sales, dept_marketing])
        count_multi = _count_list_queries()

        # The page grew (more signals, more department links), but the
        # prefetch keeps the query plan flat: the department fan-out never
        # adds a per-row query. Allow the base list machinery its own
        # constant overhead — the invariant under test is "no growth from
        # the department fan-out", i.e. B is not heavier than A.
        assert count_multi <= count_single, (
            f'usage_departments looks N+1: single-dept page={count_single} '
            f'queries, multi-dept page={count_multi} queries'
        )
