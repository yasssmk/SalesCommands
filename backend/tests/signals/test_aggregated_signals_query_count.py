# backend/tests/signals/test_aggregated_signals_query_count.py
"""
Sprint « Cycle de vie des contacts », 8g-4 (TD-256) — GET /module-signals/all/
for an activity (the Activity page's Signals band call: 8 types, page_size
100) made one `SELECT decision_cycles` per signal (an N+1: the provenance
block reads signal.decision_cycle, else source_activity.decision_cycle /
campaign / decision_step, never preloaded). The shared list queryset
(BaseSignalViewSet.get_queryset) now preloads them: the query count no
longer grows with the number of signals, and stays under a fixed bound.
Builders reused from test_aggregated_signals_endpoint.py.
"""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from tests.signals.test_aggregated_signals_endpoint import (
    _url, _mk_constraint, _mk_impact, _mk_objective, _mk_pain, _mk_people, _mk_tech, _mk_blocker,
)


pytestmark = pytest.mark.django_db

TYPES = ['pain', 'objective', 'impact', 'tech-stack', 'blockers', 'constraints', 'competitors', 'people']
BUILDERS = (_mk_pain, _mk_impact, _mk_tech, _mk_blocker, _mk_objective, _mk_people, _mk_constraint)
MAX_QUERIES = 25


def _activity_in_cycle(account, user):
    from app_modules.activities.models import Activity
    from app_modules.decision_cycles.constants import PipelineStep
    from app_modules.decision_cycles.models import DecisionCycle, DecisionStep
    dc = DecisionCycle(account=account, owner=user, name='Deal')
    dc.save(user=user, client_id=account.client_id)
    # A DC activity always sits on a step (read by the provenance block).
    step = DecisionStep(cycle=dc, name='Qualification', stage=PipelineStep.QUALIFICATION, order=1)
    step.save(user=user, client_id=account.client_id)
    a = Activity(title='Workshop', activity_type='MEETING', status='COMPLETED', account=account,
                 owner=user, decision_cycle=dc, decision_step=step, scheduled_date='2026-11-01')
    a.save(user=user, client_id=account.client_id)
    return a, dc


def _count(api, activity):
    params = {'activity_id': str(activity.id), 'signal_type': TYPES, 'page_size': 100}
    api.get(_url(), params)                       # warm the non-query caches
    with CaptureQueriesContext(connection) as ctx:
        r = api.get(_url(), params)
    assert r.status_code == 200, r.content
    return len(ctx.captured_queries), r.json().get('count')


def test_the_activity_signals_list_has_no_n_plus_one(authed_api_a, account, user_a):
    activity, dc = _activity_in_cycle(account, user_a)
    for mk in BUILDERS:
        mk(account, activity, user_a, dc)
    few, few_rows = _count(authed_api_a, activity)
    for mk in BUILDERS:
        for _ in range(4):
            mk(account, activity, user_a, dc)
    many, many_rows = _count(authed_api_a, activity)
    assert many_rows == 5 * few_rows
    assert many == few, f'{few} queries for {few_rows} signals, {many} for {many_rows}'
    assert many <= MAX_QUERIES
