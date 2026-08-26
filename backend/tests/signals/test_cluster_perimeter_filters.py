# backend/tests/signals/test_cluster_perimeter_filters.py
"""
Grouped/cluster endpoint — the unified PERIMETER filter (OR) + domain (`what`) +
dimension + multi-contact.

Perimeter (PO-locked): a single multi list [sentinel 'BUSINESS'] + department
ids, combined with OR:
    q = Q(scope_level=BUSINESS) | Q(target_department_id__in=dept_ids)
So perimeter=[BUSINESS, Marketing] returns scope=BUSINESS members OR members
targeting Marketing. This REPLACES the separate department+scope AND behaviour
on the grouped path (the old department/scope kwargs stay for back-compat).

Cluster members are only pain/objective/impact — all carry scope_level,
target_department, what and dimension — so the OR applies uniformly.

Cross-family combination is AND (perimeter AND what AND dimension AND contact
AND status); OR is only WITHIN the perimeter clause.
"""

import pytest

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


def _dept(name):
    dept, _ = StandardDepartment.objects.get_or_create(name=name)
    return dept


def _contact(account, user, first):
    from app_modules.contacts.models import Contact
    c = Contact(account=account, first_name=first, last_name="X", job_title="T")
    c.save(user=user, client_id=account.client_id)
    return c


def _activity(account, user, *contacts):
    from app_modules.activities.models import Activity
    from app_modules.activities.constants import ActivityType, ActivityStatus
    a = Activity(
        title="Call", activity_type=ActivityType.MEETING,
        status=ActivityStatus.COMPLETED, account=account, owner=user,
    )
    a.save(user=user, client_id=account.client_id)
    for c in contacts:
        a.contacts.add(c)
    return a


def _pain(account, activity, user, *, what=SignalWhat.OPS,
          dimension=SignalDimension.TIME, scope=ScopeLevel.DEPARTMENT,
          dept=None, status=SignalStatus.PENDING, quote="q"):
    is_validated = status == SignalStatus.VALIDATED
    p = PainSignal(
        account=account, source_activity=activity,
        what=what, dimension=dimension,
        summary="Reporting", source_quote=quote,
        source=SignalSource.MANUAL if is_validated else SignalSource.LLM_EXTRACTED,
        status=SignalStatus.VALIDATED if is_validated else SignalStatus.PENDING,
        scope_level=scope, target_department=dept,
    )
    p.save(user=user, client_id=account.client_id)
    return p


def _list(account, **kwargs):
    return SignalClusterService.list_clusters_for_account(
        account_id=account.id, signal_type="pain", **kwargs,
    )


def _total(clusters):
    return sum(c["signal_count"] for c in clusters)


# =============================================================================
# PERIMETER — the OR
# =============================================================================

class TestPerimeterOr:

    def test_business_or_department(self, account, activity, user_a):
        mktg, fin = _dept("Marketing"), _dept("Finance")
        _pain(account, activity, user_a, scope=ScopeLevel.BUSINESS, dept=None, quote="b")
        _pain(account, activity, user_a, scope=ScopeLevel.DEPARTMENT, dept=mktg, quote="m")
        _pain(account, activity, user_a, scope=ScopeLevel.DEPARTMENT, dept=fin, quote="f")

        clusters = _list(
            account, perimeter_business=True, perimeter_departments=[mktg.id],
        )
        # Business member OR Marketing member = 2; Finance excluded.
        assert _total(clusters) == 2

    def test_business_only(self, account, activity, user_a):
        _pain(account, activity, user_a, scope=ScopeLevel.BUSINESS, dept=None, quote="b")
        _pain(account, activity, user_a, scope=ScopeLevel.DEPARTMENT,
              dept=_dept("Marketing"), quote="m")

        clusters = _list(account, perimeter_business=True)
        # Only the scope=BUSINESS member; the Marketing member is excluded.
        assert _total(clusters) == 1

    def test_departments_only(self, account, activity, user_a):
        mktg = _dept("Marketing")
        _pain(account, activity, user_a, scope=ScopeLevel.BUSINESS, dept=None, quote="b")
        _pain(account, activity, user_a, scope=ScopeLevel.DEPARTMENT, dept=mktg, quote="m")

        clusters = _list(account, perimeter_departments=[mktg.id])
        # Only Marketing; the Business member is excluded (no BUSINESS sentinel).
        assert _total(clusters) == 1


# =============================================================================
# DOMAIN (`what`) + DIMENSION
# =============================================================================

class TestDomainDimension:

    def test_what_filters_domain(self, account, activity, user_a):
        _pain(account, activity, user_a, what=SignalWhat.DATA, quote="d")
        _pain(account, activity, user_a, what=SignalWhat.TECH, quote="t")

        clusters = _list(account, whats=[SignalWhat.DATA])
        assert _total(clusters) == 1
        assert all(c["what"] == SignalWhat.DATA for c in clusters)

    def test_dimension_filters(self, account, activity, user_a):
        _pain(account, activity, user_a, dimension=SignalDimension.QUALITY, quote="q")
        _pain(account, activity, user_a, dimension=SignalDimension.TIME, quote="t")

        clusters = _list(account, dimensions=[SignalDimension.QUALITY])
        assert _total(clusters) == 1
        assert all(c["dimension"] == SignalDimension.QUALITY for c in clusters)


# =============================================================================
# CONTACT (multi)
# =============================================================================

class TestContactMulti:

    def test_contact_list_matches_either(self, account, user_a):
        c1 = _contact(account, user_a, "Ivan")
        c2 = _contact(account, user_a, "Olga")
        c3 = _contact(account, user_a, "Nina")
        _pain(account, _activity(account, user_a, c1), user_a, quote="by1")
        _pain(account, _activity(account, user_a, c2), user_a, quote="by2")
        _pain(account, _activity(account, user_a, c3), user_a, quote="by3")

        clusters = _list(account, contacts=[str(c1.id), str(c2.id)])
        # Reported by c1 OR c2 = 2; c3 excluded. No duplicate rows.
        assert _total(clusters) == 2


# =============================================================================
# CROSS-FAMILY AND (perimeter AND what)
# =============================================================================

class TestCrossFamilyAnd:

    def test_perimeter_and_what(self, account, activity, user_a):
        mktg = _dept("Marketing")
        # Business + DATA  → matches perimeter(Business) AND what(DATA)
        _pain(account, activity, user_a, scope=ScopeLevel.BUSINESS, dept=None,
              what=SignalWhat.DATA, quote="bd")
        # Business + TECH  → matches perimeter but NOT what
        _pain(account, activity, user_a, scope=ScopeLevel.BUSINESS, dept=None,
              what=SignalWhat.TECH, quote="bt")
        # Marketing + DATA → matches what but NOT a Business-only perimeter
        _pain(account, activity, user_a, scope=ScopeLevel.DEPARTMENT, dept=mktg,
              what=SignalWhat.DATA, quote="md")

        clusters = _list(account, perimeter_business=True, whats=[SignalWhat.DATA])
        # Only the Business+DATA member.
        assert _total(clusters) == 1


# =============================================================================
# VIEW — param parsing (400 not 500)
# =============================================================================

class TestPerimeterViewParams:

    def _url(self):
        from django.urls import reverse
        return reverse("module_signals:cluster-list")

    def test_invalid_what_is_400(self, authed_api_a, account, activity, user_a):
        resp = authed_api_a.get(
            self._url(), {"account": str(account.id), "what": "BOGUS"},
        )
        assert resp.status_code == 400

    def test_invalid_dimension_is_400(self, authed_api_a, account, activity, user_a):
        resp = authed_api_a.get(
            self._url(), {"account": str(account.id), "dimension": "BOGUS"},
        )
        assert resp.status_code == 400

    def test_perimeter_bounded_queries(
        self, authed_api_a, account, activity, user_a, django_assert_max_num_queries,
    ):
        mktg = _dept("Marketing")
        for i in range(5):
            _pain(account, activity, user_a, scope=ScopeLevel.DEPARTMENT,
                  dept=mktg, quote=f"q{i}")
        with django_assert_max_num_queries(25):
            resp = authed_api_a.get(
                self._url(),
                {"account": str(account.id), "perimeter": ["BUSINESS", str(mktg.id)]},
            )
        assert resp.status_code == 200
