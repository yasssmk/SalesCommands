# backend/tests/signals/test_qualif_target_department_exposed.py
"""
A1.4: the qualification signal serializers (pain / objective / impact) must
expose scope_level AND target_department (id + name) on their List endpoints
so the UI can render the scope. A DEPARTMENT-scoped signal returns the
compact {id, name} FK shape; a BUSINESS-scoped one returns null.
"""

import pytest
from django.urls import reverse
from rest_framework import status

from app_modules.signals.constants import (
    ImpactType,
    ScopeLevel,
    SignalDimension,
    SignalSource,
    SignalWhat,
)
from app_modules.signals.models import ImpactSignal, ObjectiveSignal, PainSignal


pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def marketing_dept(db):
    from app_modules.core_modules.models import StandardDepartment
    dept, _ = StandardDepartment.objects.get_or_create(name='Marketing')
    return dept


def _results(response):
    body = response.json()
    results = body.get('results') or body.get('data', {}).get('results') or body
    if isinstance(results, dict):
        results = results.get('results', results)
    return results


def _row(response, signal_id):
    return next(r for r in _results(response) if r['id'] == str(signal_id))


class TestTargetDepartmentExposed:

    def test_pain_list_exposes_scope_and_department(
        self, authed_api_a, account, activity, user_a, marketing_dept,
    ):
        p = PainSignal(
            account=account, source_activity=activity,
            source=SignalSource.LLM_EXTRACTED,
            what=SignalWhat.DATA, dimension=SignalDimension.QUALITY,
            scope_level=ScopeLevel.DEPARTMENT,
            summary='Marketing data quality is poor',
            source_quote='the marketing data is unreliable',
        )
        p.save(user=user_a, client_id=account.client_id)
        p.target_departments.set([marketing_dept])  # sub-step 2b: M2M scope

        resp = authed_api_a.get(
            reverse('module_signals:pain-list'),
            {'source_activity': str(activity.id)},
        )
        assert resp.status_code == status.HTTP_200_OK
        row = _row(resp, p.id)
        assert row['scope_level'] == ScopeLevel.DEPARTMENT
        assert row['target_departments'] == [{
            'id': str(marketing_dept.id),
            'name': marketing_dept.get_name_display(),
        }]

    def test_pain_list_business_scope_has_null_department(
        self, authed_api_a, account, activity, user_a,
    ):
        p = PainSignal(
            account=account, source_activity=activity,
            source=SignalSource.LLM_EXTRACTED,
            what=SignalWhat.OPS, dimension=SignalDimension.TIME,
            scope_level=ScopeLevel.BUSINESS,
            summary='Company-wide reporting is slow',
            source_quote='reporting takes three weeks',
        )
        p.save(user=user_a, client_id=account.client_id)

        resp = authed_api_a.get(
            reverse('module_signals:pain-list'),
            {'source_activity': str(activity.id)},
        )
        assert resp.status_code == status.HTTP_200_OK
        row = _row(resp, p.id)
        assert row['scope_level'] == ScopeLevel.BUSINESS
        assert row['target_departments'] == []

    def test_objective_list_exposes_scope_and_department(
        self, authed_api_a, account, activity, user_a, marketing_dept,
    ):
        o = ObjectiveSignal(
            account=account, source_activity=activity,
            source=SignalSource.LLM_EXTRACTED,
            what=SignalWhat.DATA, dimension=SignalDimension.QUALITY,
            scope_level=ScopeLevel.DEPARTMENT, target_department=marketing_dept,
            summary='Improve marketing data quality',
            source_quote='marketing wants clean data',
        )
        o.save(user=user_a, client_id=account.client_id)

        resp = authed_api_a.get(
            reverse('module_signals:objective-list'),
            {'source_activity': str(activity.id)},
        )
        assert resp.status_code == status.HTTP_200_OK
        row = _row(resp, o.id)
        assert row['scope_level'] == ScopeLevel.DEPARTMENT
        assert row['target_department'] == {
            'id': str(marketing_dept.id),
            'name': marketing_dept.get_name_display(),
        }

    def test_impact_list_exposes_scope_and_department(
        self, authed_api_a, account, activity, user_a, marketing_dept,
    ):
        i = ImpactSignal(
            account=account, source_activity=activity,
            source=SignalSource.LLM_EXTRACTED,
            what=SignalWhat.DATA, dimension=SignalDimension.QUALITY,
            impact_type=ImpactType.PRODUCTIVITY,
            scope_level=ScopeLevel.DEPARTMENT,
            summary='Marketing loses time on bad data',
            source_quote='marketing spends 6h/week cleaning data',
        )
        i.save(user=user_a, client_id=account.client_id)
        i.target_departments.set([marketing_dept])  # sub-step 2b: M2M scope

        resp = authed_api_a.get(
            reverse('module_signals:impact-list'),
            {'source_activity': str(activity.id)},
        )
        assert resp.status_code == status.HTTP_200_OK
        row = _row(resp, i.id)
        assert row['scope_level'] == ScopeLevel.DEPARTMENT
        assert row['target_departments'] == [{
            'id': str(marketing_dept.id),
            'name': marketing_dept.get_name_display(),
        }]
