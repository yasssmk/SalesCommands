# backend/tests/activities/test_activity_stakeholders_query_count.py
"""
Sprint « Cycle de vie des contacts », 8g-6d — GET /module-activities/{id}/
serialises stakeholders_detail: per stakeholder its department, its contact
and (8g-6b) its role read on current_signal — one query each per stakeholder
(an N+1). The detail queryset now preloads stakeholders → current_signal /
department / contact, and the preload survives the endpoint's get_object
(no refetch): the query count no longer grows with the stakeholders.
"""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from app_modules.core_modules.models import StandardDepartment
from tests.signals.test_signal_cycle_attachment import _cycle, _people, _plain_activity


pytestmark = pytest.mark.django_db


def _add_stakeholders(activity, cycle, user, n, start=0):
    from app_modules.decision_cycles.models import Stakeholder
    dept, _ = StandardDepartment.objects.get_or_create(name=StandardDepartment.DepartmentChoices.SALES)
    for i in range(start, start + n):
        signal = _people(activity, user, f'Person {i}', decision_cycle=cycle)
        st = Stakeholder(decision_cycle=cycle, full_name=f'Person {i}', department=dept,
                         current_signal=signal)
        st.save(user=user, client_id=cycle.client_id)
        activity.stakeholders.add(st)


def _count(api, activity):
    api.get(f'/module-activities/{activity.id}/')            # warm the non-query caches
    with CaptureQueriesContext(connection) as ctx:
        r = api.get(f'/module-activities/{activity.id}/')
    assert r.status_code == 200, r.content
    body = r.json()
    return len(ctx.captured_queries), len(body.get('data', body)['stakeholders_detail'])


def test_the_activity_detail_has_no_stakeholder_n_plus_one(authed_api_a, account, user_a):
    cycle = _cycle(account, user_a)
    activity = _plain_activity(account, user_a)
    _add_stakeholders(activity, cycle, user_a, 1)
    few, few_rows = _count(authed_api_a, activity)
    _add_stakeholders(activity, cycle, user_a, 3, start=1)
    many, many_rows = _count(authed_api_a, activity)
    assert (few_rows, many_rows) == (1, 4)
    assert many == few, f'{few} queries for {few_rows} stakeholder(s), {many} for {many_rows}'
