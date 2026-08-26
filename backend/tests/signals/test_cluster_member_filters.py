# backend/tests/signals/test_cluster_member_filters.py
"""
Cluster member filters (department / contact / scope / status) on the grouped
(cluster) endpoint.

Locked semantics (two DISTINCT axes on different fields):
  * department (multi) filters on the SUBJECT = target_department (which
    department the signal is ABOUT). "IT says Marketing has a problem" → the
    signal's target_department is Marketing → it matches department=Marketing,
    NOT department=IT. Business members (no target_department) are EXCLUDED when
    a department filter is set.
  * contact filters on the SOURCE = source_activity.contacts (who reported it).
    The same "IT-reported Marketing" signal matches contact=<IT person> because
    IT reported it, regardless of its subject.
  * scope filters on scope_level.
  * status filters on status (default pending+validated).
Independent AND filters. The cluster re-forms on the filtered members and its
meta (signal_count, departments, …) recomputes on that filtered set; a cluster
with zero matching members is not returned.
"""

import pytest
from django.urls import reverse

from app_modules.core_modules.models import StandardDepartment
from app_modules.signals.constants import (
    ScopeLevel,
    SignalDimension,
    SignalSource,
    SignalStatus,
    SignalWhat,
)
from app_modules.signals.models import PainSignal
from app_modules.signals.services import SignalClusterService


pytestmark = pytest.mark.django_db


# =============================================================================
# HELPERS
# =============================================================================

def _dept(name):
    dept, _ = StandardDepartment.objects.get_or_create(name=name)
    return dept


def _activity(account, user, *contacts):
    from app_modules.activities.models import Activity
    from app_modules.activities.constants import ActivityType, ActivityStatus
    a = Activity(
        title='Call', activity_type=ActivityType.MEETING,
        status=ActivityStatus.COMPLETED, account=account, owner=user,
    )
    a.save(user=user, client_id=account.client_id)
    for c in contacts:
        a.contacts.add(c)
    return a


def _contact(account, user, first, title):
    from app_modules.contacts.models import Contact
    c = Contact(account=account, first_name=first, last_name='X', job_title=title)
    c.save(user=user, client_id=account.client_id)
    return c


def _pain(account, activity, user, *, dept=None, scope=ScopeLevel.DEPARTMENT,
          status=SignalStatus.PENDING, quote='q'):
    """
    PainSignal on the SAME canonical cluster (OPS x TIME). VALIDATED via MANUAL
    (force-validated), PENDING via LLM_EXTRACTED. Distinct source_quote lets
    several members coexist in the one cluster.
    """
    is_validated = status == SignalStatus.VALIDATED
    p = PainSignal(
        account=account, source_activity=activity,
        what=SignalWhat.OPS, dimension=SignalDimension.TIME,
        summary='Reporting is slow', source_quote=quote,
        source=SignalSource.MANUAL if is_validated else SignalSource.LLM_EXTRACTED,
        status=SignalStatus.VALIDATED if is_validated else SignalStatus.PENDING,
        scope_level=scope, target_department=dept,
    )
    p.save(user=user, client_id=account.client_id)
    return p


def _list(account, **kwargs):
    return SignalClusterService.list_clusters_for_account(
        account_id=account.id, signal_type='pain', **kwargs,
    )


# =============================================================================
# DEPARTMENT — filters on the SUBJECT (target_department)
# =============================================================================

class TestDepartmentFilter:

    def test_department_matches_subject_excludes_other_dept_and_business(
        self, account, activity, user_a,
    ):
        mktg, it = _dept('Marketing'), _dept('IT')
        _pain(account, activity, user_a, dept=mktg, quote='m1')   # subject Marketing
        _pain(account, activity, user_a, dept=it, quote='i1')     # subject IT
        _pain(account, activity, user_a, dept=None,
              scope=ScopeLevel.BUSINESS, quote='b1')              # business

        clusters = _list(account, departments=[mktg.id])
        assert len(clusters) == 1
        c = clusters[0]
        assert c['signal_count'] == 1  # only the Marketing-subject member
        dept_ids = {d['id'] for d in c['departments']}
        assert dept_ids == {str(mktg.id)}  # meta recomputed on filtered members

    def test_it_reported_marketing_matches_department_marketing(
        self, account, user_a,
    ):
        # "IT says Marketing has a problem" — subject is Marketing even though an
        # IT person reported it. department=Marketing MUST include it.
        mktg = _dept('Marketing')
        it_person = _contact(account, user_a, 'Ivan', 'IT Lead')
        act = _activity(account, user_a, it_person)  # reported by IT
        _pain(account, act, user_a, dept=mktg, quote='itm')

        clusters = _list(account, departments=[mktg.id])
        assert len(clusters) == 1
        assert clusters[0]['signal_count'] == 1


# =============================================================================
# CONTACT — filters on the SOURCE (who reported), not the subject
# =============================================================================

class TestContactFilter:

    def test_contact_matches_source_not_subject(self, account, user_a):
        mktg = _dept('Marketing')
        it_person = _contact(account, user_a, 'Ivan', 'IT Lead')
        other = _contact(account, user_a, 'Olga', 'Ops')
        act_it = _activity(account, user_a, it_person)
        act_other = _activity(account, user_a, other)

        # Both signals have SUBJECT Marketing; they differ only in who reported.
        _pain(account, act_it, user_a, dept=mktg, quote='byIT')
        _pain(account, act_other, user_a, dept=mktg, quote='byOther')

        clusters = _list(account, contact=str(it_person.id))
        assert len(clusters) == 1
        # Only the IT-reported one — proves contact filters SOURCE, not subject
        # (both share subject Marketing).
        assert clusters[0]['signal_count'] == 1


# =============================================================================
# SCOPE
# =============================================================================

class TestScopeFilter:

    def test_scope_department_excludes_business(self, account, activity, user_a):
        _pain(account, activity, user_a, dept=_dept('Marketing'),
              scope=ScopeLevel.DEPARTMENT, quote='d1')
        _pain(account, activity, user_a, dept=None,
              scope=ScopeLevel.BUSINESS, quote='b1')

        clusters = _list(account, scope=ScopeLevel.DEPARTMENT)
        assert len(clusters) == 1
        assert clusters[0]['signal_count'] == 1


# =============================================================================
# STATUS + AND-combination
# =============================================================================

class TestStatusAndCombination:

    def test_department_and_status_pending_is_and(self, account, activity, user_a):
        mktg = _dept('Marketing')
        _pain(account, activity, user_a, dept=mktg,
              status=SignalStatus.PENDING, quote='p1')
        _pain(account, activity, user_a, dept=mktg,
              status=SignalStatus.VALIDATED, quote='v1')

        clusters = _list(account, departments=[mktg.id],
                         statuses=[SignalStatus.PENDING])
        assert len(clusters) == 1
        c = clusters[0]
        assert c['signal_count'] == 1
        assert c['pending_count'] == 1
        assert c['confirmation_count'] == 0


# =============================================================================
# META recompute + empty-after-filter
# =============================================================================

class TestMetaAndEmpty:

    def test_cluster_meta_reflects_filtered_members(self, account, activity, user_a):
        mktg, it = _dept('Marketing'), _dept('IT')
        _pain(account, activity, user_a, dept=mktg, quote='m1')
        _pain(account, activity, user_a, dept=it, quote='i1')

        # Unfiltered: one cluster, both departments, count 2.
        full = _list(account)
        assert full[0]['signal_count'] == 2
        assert {d['id'] for d in full[0]['departments']} == {str(mktg.id), str(it.id)}

        # Filtered: meta recomputes on the Marketing member only.
        filtered = _list(account, departments=[mktg.id])
        assert filtered[0]['signal_count'] == 1
        assert {d['id'] for d in filtered[0]['departments']} == {str(mktg.id)}

    def test_zero_matching_members_returns_no_cluster(self, account, activity, user_a):
        _pain(account, activity, user_a, dept=_dept('IT'), quote='i1')
        clusters = _list(account, departments=[_dept('Marketing').id])
        assert clusters == []


# =============================================================================
# VIEW — param parsing (clean 400, never 500) + bounded queries
# =============================================================================

class TestClusterViewParams:

    def _url(self):
        return reverse('module_signals:cluster-list')

    def test_invalid_department_is_400_not_500(
        self, authed_api_a, account, activity, user_a,
    ):
        resp = authed_api_a.get(
            self._url(), {'account': str(account.id), 'department': 'not-an-int'},
        )
        assert resp.status_code == 400

    def test_invalid_scope_is_400_not_500(
        self, authed_api_a, account, activity, user_a,
    ):
        resp = authed_api_a.get(
            self._url(), {'account': str(account.id), 'scope': 'GALAXY'},
        )
        assert resp.status_code == 400

    def test_filtered_list_query_count_bounded(
        self, authed_api_a, account, activity, user_a, django_assert_max_num_queries,
    ):
        mktg = _dept('Marketing')
        for i in range(5):
            _pain(account, activity, user_a, dept=mktg, quote=f'q{i}')
        # Bounded — not O(members). Auth/permission adds a fixed overhead.
        with django_assert_max_num_queries(25):
            resp = authed_api_a.get(
                self._url(),
                {'account': str(account.id), 'department': str(mktg.id)},
            )
        assert resp.status_code == 200
