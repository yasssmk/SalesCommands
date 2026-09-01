# backend/tests/signals/test_constraint_departments_m2m.py
"""
Sub-step 1b — Constraint scope readers move from the single FK
target_department to the multi-department M2M target_departments.

These tests exercise the REAL paths (serializer via API, cluster service,
aggregated endpoint) with a ConstraintSignal that carries TWO departments in
target_departments and NO value on the legacy FK. They are RED before the
recabling (the readers only look at the FK, so they see zero departments) and
GREEN once each reader reads the M2M.

Only Constraint is recabled here; pain/impact/objective/people stay on the FK
(covered by their own untouched tests).
"""

import pytest
from rest_framework import status
from django.urls import reverse

from app_modules.signals.constants import (
    ConstraintNature,
    Rigidity,
    SignalSource,
    SignalStatus,
)
from app_modules.signals.models import ConstraintSignal
from app_modules.signals.services import SignalClusterService


CONSTRAINT_URL = '/module-signals/constraints/'


def _dept(name):
    from app_modules.core_modules.models import StandardDepartment
    d, _ = StandardDepartment.objects.get_or_create(name=name)
    return d


def _mk_constraint_m2m(account, activity, user_a, depts, *,
                       decision_cycle=None, nature=ConstraintNature.TECHNICAL,
                       source=SignalSource.MANUAL, summary='A requirement'):
    """Persist a ConstraintSignal, then attach `depts` to the M2M (post-save).
    The legacy FK target_department is deliberately left NULL."""
    sig = ConstraintSignal(
        account=account,
        source_activity=activity,
        decision_cycle=decision_cycle,
        nature=nature,
        summary=summary,
        rigidity=Rigidity.FIRM,
        source=source,
    )
    sig.save(user=user_a, client_id=account.client_id)
    sig.target_departments.set(depts)
    return sig


def _results(body):
    """Extract the row list from a (possibly paginated / enveloped) response."""
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
class TestConstraintSerializerReadM2M:

    def test_detail_exposes_all_target_departments(
        self, authed_api_a, account, activity, user_a,
    ):
        fin, it = _dept('Finance'), _dept('IT')
        sig = _mk_constraint_m2m(account, activity, user_a, [fin, it])

        resp = authed_api_a.get(f'{CONSTRAINT_URL}{sig.id}/')
        assert resp.status_code == status.HTTP_200_OK

        payload = resp.json()
        payload = payload.get('data', payload) if isinstance(payload, dict) else payload
        names = {d['name'] for d in payload['target_departments']}
        assert names == {fin.get_name_display(), it.get_name_display()}


@pytest.mark.django_db
class TestConstraintSerializerWriteM2M:

    def test_create_accepts_target_departments_list(
        self, authed_api_a, account, activity,
    ):
        fin, it = _dept('Finance'), _dept('IT')
        payload = {
            'signal_type': 'constraint',
            'source': 'MANUAL',
            'account': str(account.id),
            'source_activity': str(activity.id),
            'nature': ConstraintNature.TECHNICAL,
            'summary': 'Must integrate with SAP',
            'rigidity': Rigidity.FIRM,
            'target_departments': [str(fin.id), str(it.id)],
        }
        resp = authed_api_a.post(CONSTRAINT_URL, payload, format='json')
        assert resp.status_code == status.HTTP_201_CREATED
        pk = resp.json()['data']['id']

        sig = ConstraintSignal.objects.get(pk=pk)
        assert set(sig.target_departments.values_list('id', flat=True)) == {fin.id, it.id}

    def test_patch_empty_list_clears_departments(
        self, authed_api_a, account, activity, user_a,
    ):
        fin, it = _dept('Finance'), _dept('IT')
        sig = _mk_constraint_m2m(account, activity, user_a, [fin, it])

        resp = authed_api_a.patch(
            f'{CONSTRAINT_URL}{sig.id}/',
            {'target_departments': []},
            format='json',
        )
        assert resp.status_code == status.HTTP_200_OK
        sig.refresh_from_db()
        assert list(sig.target_departments.all()) == []


@pytest.mark.django_db
class TestConstraintClusterDepartmentsM2M:

    def test_cluster_aggregates_all_departments_from_m2m(
        self, account, activity, decision_cycle, user_a,
    ):
        fin, it = _dept('Finance'), _dept('IT')
        _mk_constraint_m2m(
            account, activity, user_a, [fin, it],
            decision_cycle=decision_cycle,
        )

        clusters = SignalClusterService.list_clusters_for_account(
            account_id=account.id,
            signal_type='constraint',
            decision_cycle_id=decision_cycle.id,
        )
        names = {d['name'] for d in clusters[0]['departments']}
        assert names == {fin.get_name_display(), it.get_name_display()}


@pytest.mark.django_db
class TestConstraintAggregatedFilterM2M:

    def test_department_filter_matches_each_of_two(
        self, authed_api_a, account, activity, decision_cycle, user_a,
    ):
        fin, it = _dept('Finance'), _dept('IT')
        sig = _mk_constraint_m2m(
            account, activity, user_a, [fin, it],
            decision_cycle=decision_cycle,
        )

        url = reverse('module_signals:signal-all')
        for dept in (fin, it):
            resp = authed_api_a.get(url, {
                'decision_cycle_id': str(decision_cycle.id),
                'department': str(dept.id),
                'signal_type': 'constraints',
            })
            assert resp.status_code == status.HTTP_200_OK
            ids = {str(row.get('id')) for row in _results(resp.json())}
            assert str(sig.id) in ids, f"constraint not matched on department {dept.name}"
