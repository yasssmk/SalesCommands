# backend/tests/signals/test_pain_impact_departments_m2m.py
"""
Sub-step 2b — Pain and Impact scope readers move from the single FK
target_department to the multi-department M2M target_departments.

Exercises the REAL paths (serializer via API, cluster service incl. the
perimeter/department filter, aggregated endpoint) with a PainSignal and an
ImpactSignal carrying TWO departments in target_departments and NO value on
the legacy FK. RED before the recabling (readers see zero departments), GREEN
once each reader reads the M2M.

Objective (which stays on its FK) is exercised as a non-regression guard: its
single-department FK output must be unchanged.
"""

import pytest
from rest_framework import status
from django.urls import reverse

from app_modules.signals.constants import (
    ScopeLevel,
    SignalDimension,
    SignalSource,
    SignalStatus,
    SignalWhat,
    ImpactType,
)
from app_modules.signals.models import PainSignal, ImpactSignal, ObjectiveSignal
from app_modules.signals.services import SignalClusterService


def _dept(name):
    from app_modules.core_modules.models import StandardDepartment
    d, _ = StandardDepartment.objects.get_or_create(name=name)
    return d


def _mk_pain(account, activity, user_a, depts, *, decision_cycle=None,
             what=SignalWhat.OPS, dimension=SignalDimension.TIME):
    p = PainSignal(
        account=account, source_activity=activity, decision_cycle=decision_cycle,
        what=what, dimension=dimension, scope_level=ScopeLevel.DEPARTMENT,
        summary='Reporting pain', source_quote='q', source=SignalSource.MANUAL,
    )
    p.save(user=user_a, client_id=account.client_id)
    p.target_departments.set(depts)
    return p


def _mk_impact(account, activity, user_a, depts, *, decision_cycle=None,
               what=SignalWhat.OPS, dimension=SignalDimension.TIME):
    i = ImpactSignal(
        account=account, source_activity=activity, decision_cycle=decision_cycle,
        what=what, dimension=dimension, scope_level=ScopeLevel.DEPARTMENT,
        impact_type=ImpactType.FINANCIAL, summary='Cost impact',
        source_quote='q', source=SignalSource.MANUAL,
    )
    i.save(user=user_a, client_id=account.client_id)
    i.target_departments.set(depts)
    return i


def _results(body):
    if isinstance(body, dict):
        if 'results' in body:
            return body['results']
        data = body.get('data')
        if isinstance(data, dict) and 'results' in data:
            return data['results']
        if isinstance(data, list):
            return data
    return body


@pytest.mark.django_db
class TestPainImpactSerializerReadM2M:

    def test_pain_detail_exposes_all_departments(self, authed_api_a, account, activity, user_a):
        fin, it = _dept('Finance'), _dept('IT')
        p = _mk_pain(account, activity, user_a, [fin, it])
        resp = authed_api_a.get(reverse('module_signals:pain-detail', args=[p.id]))
        assert resp.status_code == status.HTTP_200_OK
        payload = resp.json()
        payload = payload.get('data', payload) if isinstance(payload, dict) else payload
        names = {d['name'] for d in payload['target_departments']}
        assert names == {fin.get_name_display(), it.get_name_display()}

    def test_impact_detail_exposes_all_departments(self, authed_api_a, account, activity, user_a):
        fin, it = _dept('Finance'), _dept('IT')
        i = _mk_impact(account, activity, user_a, [fin, it])
        resp = authed_api_a.get(reverse('module_signals:impact-detail', args=[i.id]))
        assert resp.status_code == status.HTTP_200_OK
        payload = resp.json()
        payload = payload.get('data', payload) if isinstance(payload, dict) else payload
        names = {d['name'] for d in payload['target_departments']}
        assert names == {fin.get_name_display(), it.get_name_display()}


@pytest.mark.django_db
class TestPainImpactClusterDepartmentsM2M:

    def test_pain_cluster_aggregates_both(self, account, activity, decision_cycle, user_a):
        fin, it = _dept('Finance'), _dept('IT')
        _mk_pain(account, activity, user_a, [fin, it], decision_cycle=decision_cycle)
        clusters = SignalClusterService.list_clusters_for_account(
            account_id=account.id, signal_type='pain', decision_cycle_id=decision_cycle.id,
        )
        names = {d['name'] for d in clusters[0]['departments']}
        assert names == {fin.get_name_display(), it.get_name_display()}

    def test_impact_cluster_aggregates_both(self, account, activity, decision_cycle, user_a):
        fin, it = _dept('Finance'), _dept('IT')
        _mk_impact(account, activity, user_a, [fin, it], decision_cycle=decision_cycle)
        clusters = SignalClusterService.list_clusters_for_account(
            account_id=account.id, signal_type='impact', decision_cycle_id=decision_cycle.id,
        )
        names = {d['name'] for d in clusters[0]['departments']}
        assert names == {fin.get_name_display(), it.get_name_display()}


@pytest.mark.django_db
class TestPainPerimeterFilterM2M:

    def test_perimeter_department_matches_each(self, account, activity, decision_cycle, user_a):
        fin, it = _dept('Finance'), _dept('IT')
        _mk_pain(account, activity, user_a, [fin, it], decision_cycle=decision_cycle)
        for dept in (fin, it):
            clusters = SignalClusterService.list_clusters_for_account(
                account_id=account.id, signal_type='pain',
                decision_cycle_id=decision_cycle.id, perimeter_departments=[dept.id],
            )
            total = sum(c['signal_count'] for c in clusters)
            assert total == 1, f"pain not matched on perimeter department {dept.name}"


@pytest.mark.django_db
class TestPainImpactAggregatedFilterM2M:

    def test_pain_department_filter_matches_each(self, authed_api_a, account, activity, decision_cycle, user_a):
        fin, it = _dept('Finance'), _dept('IT')
        p = _mk_pain(account, activity, user_a, [fin, it], decision_cycle=decision_cycle)
        url = reverse('module_signals:signal-all')
        for dept in (fin, it):
            resp = authed_api_a.get(url, {
                'decision_cycle_id': str(decision_cycle.id),
                'department': str(dept.id), 'signal_type': 'pain',
            })
            assert resp.status_code == status.HTTP_200_OK
            ids = {str(r.get('id')) for r in _results(resp.json())}
            assert str(p.id) in ids, f"pain not matched on department {dept.name}"

    def test_impact_department_filter_matches_each(self, authed_api_a, account, activity, decision_cycle, user_a):
        fin, it = _dept('Finance'), _dept('IT')
        i = _mk_impact(account, activity, user_a, [fin, it], decision_cycle=decision_cycle)
        url = reverse('module_signals:signal-all')
        for dept in (fin, it):
            resp = authed_api_a.get(url, {
                'decision_cycle_id': str(decision_cycle.id),
                'department': str(dept.id), 'signal_type': 'impact',
            })
            assert resp.status_code == status.HTTP_200_OK
            ids = {str(r.get('id')) for r in _results(resp.json())}
            assert str(i.id) in ids, f"impact not matched on department {dept.name}"


@pytest.mark.django_db
class TestObjectiveNotAffected:
    """Objective stays on the single FK target_department — unchanged output."""

    def _mk_objective(self, account, activity, user_a, dept, *, decision_cycle=None):
        o = ObjectiveSignal(
            account=account, source_activity=activity, decision_cycle=decision_cycle,
            what=SignalWhat.GROWTH, dimension=SignalDimension.TIME,
            scope_level=ScopeLevel.DEPARTMENT, summary='Grow', source_quote='q',
            source=SignalSource.MANUAL, target_department=dept,
        )
        o.save(user=user_a, client_id=account.client_id)
        return o

    def test_objective_serializer_still_exposes_single_fk_department(
        self, authed_api_a, account, activity, user_a,
    ):
        fin = _dept('Finance')
        o = self._mk_objective(account, activity, user_a, fin)
        resp = authed_api_a.get(reverse('module_signals:objective-detail', args=[o.id]))
        assert resp.status_code == status.HTTP_200_OK
        payload = resp.json()
        payload = payload.get('data', payload) if isinstance(payload, dict) else payload
        assert payload['target_department'] == {
            'id': str(fin.id), 'name': fin.get_name_display(),
        }

    def test_objective_aggregated_filter_uses_fk(
        self, authed_api_a, account, activity, decision_cycle, user_a,
    ):
        fin = _dept('Finance')
        o = self._mk_objective(account, activity, user_a, fin, decision_cycle=decision_cycle)
        url = reverse('module_signals:signal-all')
        resp = authed_api_a.get(url, {
            'decision_cycle_id': str(decision_cycle.id),
            'department': str(fin.id), 'signal_type': 'objective',
        })
        assert resp.status_code == status.HTTP_200_OK
        ids = {str(r.get('id')) for r in _results(resp.json())}
        assert str(o.id) in ids
