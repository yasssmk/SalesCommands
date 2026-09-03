# backend/tests/signals/test_cluster_departments.py
"""
Tests for the FACTUAL `departments` aggregate on a signal cluster (C4).

Each cluster exposes the DISTINCT target_department values across its member
signals — a plain list of {id, name}, not a score. Members with no department
(BUSINESS scope) do not contribute. Reuses the existing compact
target_department shape ({id: str, name: display}).
"""

import pytest

from app_modules.core_modules.models import StandardDepartment
from app_modules.signals.constants import (
    ScopeLevel,
    SignalDimension,
    SignalSource,
    SignalWhat,
)
from app_modules.signals.models import PainSignal
from app_modules.signals.serializers import SignalClusterListSerializer
from app_modules.signals.services import SignalClusterService


pytestmark = pytest.mark.django_db


# =============================================================================
# HELPERS
# =============================================================================

def _dept(name):
    dept, _ = StandardDepartment.objects.get_or_create(name=name)
    return dept


def _make_pain(account, activity, user_a, *, scope_level, department=None):
    """
    Create a VALIDATED PainSignal (MANUAL source is force-validated) on
    (OPS x TIME) so all land in the same canonical cluster.
    """
    pain = PainSignal(
        account=account,
        source_activity=activity,
        what=SignalWhat.OPS,
        dimension=SignalDimension.TIME,
        summary='Reporting is slow',
        source_quote='it takes hours every week',
        source=SignalSource.MANUAL,
        scope_level=scope_level,
    )
    pain.save(user=user_a, client_id=account.client_id)
    # sub-step 2b: the cluster departments aggregate reads the M2M.
    if department:
        pain.target_departments.set([department])
    return pain


def _cluster(account):
    clusters = SignalClusterService.list_clusters_for_account(
        account_id=account.id,
        signal_type='pain',
    )
    assert len(clusters) == 1
    return clusters[0]


# =============================================================================
# DISTINCT DEPARTMENTS ACROSS MEMBERS
# =============================================================================

class TestClusterDepartments:

    def test_distinct_departments_across_members(
        self, account, activity, user_a,
    ):
        marketing = _dept(StandardDepartment.DepartmentChoices.MARKETING)
        it = _dept(StandardDepartment.DepartmentChoices.IT)

        # 3 Marketing + 2 IT members — five signals, two distinct departments.
        for _ in range(3):
            _make_pain(
                account, activity, user_a,
                scope_level=ScopeLevel.DEPARTMENT, department=marketing,
            )
        for _ in range(2):
            _make_pain(
                account, activity, user_a,
                scope_level=ScopeLevel.DEPARTMENT, department=it,
            )

        cluster = _cluster(account)
        names = [d['name'] for d in cluster['departments']]

        # Distinct (deduped), order stable (Marketing seen first).
        assert names == [
            marketing.get_name_display(),
            it.get_name_display(),
        ]
        # Compact shape reused: {id, name}.
        assert set(cluster['departments'][0].keys()) == {'id', 'name'}

    def test_all_business_scope_has_no_departments(
        self, account, activity, user_a,
    ):
        for _ in range(3):
            _make_pain(
                account, activity, user_a,
                scope_level=ScopeLevel.BUSINESS, department=None,
            )
        cluster = _cluster(account)
        assert cluster['departments'] == []

    def test_business_plus_one_department_lists_only_that_department(
        self, account, activity, user_a,
    ):
        finance = _dept(StandardDepartment.DepartmentChoices.FINANCE)
        _make_pain(
            account, activity, user_a,
            scope_level=ScopeLevel.BUSINESS, department=None,
        )
        _make_pain(
            account, activity, user_a,
            scope_level=ScopeLevel.DEPARTMENT, department=finance,
        )
        cluster = _cluster(account)
        names = [d['name'] for d in cluster['departments']]
        assert names == [finance.get_name_display()]

    def test_departments_exposed_through_the_serializer(
        self, account, activity, user_a,
    ):
        marketing = _dept(StandardDepartment.DepartmentChoices.MARKETING)
        _make_pain(
            account, activity, user_a,
            scope_level=ScopeLevel.DEPARTMENT, department=marketing,
        )
        cluster = _cluster(account)
        data = SignalClusterListSerializer(cluster).data
        assert [d['name'] for d in data['departments']] == [
            marketing.get_name_display(),
        ]


# =============================================================================
# QUERY-COUNT BOUND — departments come from already-loaded members
# =============================================================================

class TestDepartmentsQueryBounded:

    def test_department_access_is_not_n_plus_one(
        self, account, activity, user_a, django_assert_max_num_queries,
    ):
        marketing = _dept(StandardDepartment.DepartmentChoices.MARKETING)
        it = _dept(StandardDepartment.DepartmentChoices.IT)
        for dept in (marketing, it, marketing, it, marketing):
            _make_pain(
                account, activity, user_a,
                scope_level=ScopeLevel.DEPARTMENT, department=dept,
            )

        # Building the cluster (incl. departments) must not fan out one query
        # per member for target_department — it is select_related in the fetch.
        with django_assert_max_num_queries(15):
            clusters = SignalClusterService.list_clusters_for_account(
                account_id=account.id,
                signal_type='pain',
            )
            _ = [c['departments'] for c in clusters]
