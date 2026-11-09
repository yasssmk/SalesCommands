# backend/tests/ai_pipelines/test_extraction_cache_replay_query_count.py
"""
Sprint « Cycle de vie des contacts », 8g-5 (TD-12) — the replay of an
already-extracted qualification run (POST /module-ai-pipelines/activity-
extraction/run/ → 409 ALREADY_EXTRACTED with the cached signals) re-queried
the 7 signal types bare: every detail serializer field (provenance, audit
users, per-type FKs) then cost one query per signal. The replay now reuses
each type ViewSet's queryset (the aggregated view's pattern): the query count
no longer grows with the number of cached signals.
Builders reused from tests/signals/test_aggregated_signals_endpoint.py.
"""

import hashlib

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from app_modules.ai_pipelines.constants import AIPipelineStatus, AIPipelineType
from tests.signals.test_aggregated_signals_endpoint import (
    _mk_blocker, _mk_constraint, _mk_impact, _mk_objective, _mk_pain, _mk_people, _mk_tech,
)


pytestmark = pytest.mark.django_db

URL = '/module-ai-pipelines/activity-extraction/run/'
TRANSCRIPT = 'Paul: our reporting takes three weeks every quarter and we lose data on the way.'
BUILDERS = (_mk_pain, _mk_impact, _mk_tech, _mk_blocker, _mk_objective, _mk_people, _mk_constraint)


def _activity_in_cycle(account, user):
    """A DC activity on a step — the provenance the detail serializers read."""
    from app_modules.activities.models import Activity
    from app_modules.decision_cycles.constants import PipelineStep
    from app_modules.decision_cycles.models import DecisionCycle, DecisionStep
    dc = DecisionCycle(account=account, owner=user, name='Deal')
    dc.save(user=user, client_id=account.client_id)
    step = DecisionStep(cycle=dc, name='Qualification', stage=PipelineStep.QUALIFICATION, order=1)
    step.save(user=user, client_id=account.client_id)
    a = Activity(title='Workshop', activity_type='MEETING', status='COMPLETED', account=account,
                 owner=user, decision_cycle=dc, decision_step=step, scheduled_date='2026-11-01')
    a.save(user=user, client_id=account.client_id)
    return a


def _qualification_run(activity, user):
    from app_modules.ai_pipelines.models import AIPipelineRun
    return AIPipelineRun.objects.create(
        pipeline_type=AIPipelineType.TRANSCRIPT_SIGNALS, prompt_versions={'system': 'v1'},
        provider='openai', model_name='gpt-4o-mini', temperature=0.0, source_activity=activity,
        input_hash=hashlib.sha256(TRANSCRIPT.encode('utf-8')).hexdigest(),
        status=AIPipelineStatus.SUCCESS, sub_calls=[], total_tokens_used=100, total_duration_ms=500,
        error_message='', created_signals_count=0, client_id=activity.client_id,
        created_by=user, updated_by=user,
    )


def _cached_signals(activity, user, run, per_type):
    for mk in BUILDERS:
        for _ in range(per_type):
            signal = mk(activity.account, activity, user)
            type(signal).objects.filter(pk=signal.pk).update(source_run=run)


def _replay(api, activity):
    with CaptureQueriesContext(connection) as ctx:
        r = api.post(URL, {'activity_id': str(activity.id), 'transcript': TRANSCRIPT,
                           'run_next_steps': False}, format='json')
    assert r.status_code == 409, r.content
    signals = r.json()['data']['qualification_signals']
    return len(ctx.captured_queries), sum(len(v) for v in signals.values())


def test_the_cached_replay_has_no_n_plus_one(authed_api_a, account, user_a):
    activity = _activity_in_cycle(account, user_a)
    run = _qualification_run(activity, user_a)
    _cached_signals(activity, user_a, run, 1)
    few, few_rows = _replay(authed_api_a, activity)
    _cached_signals(activity, user_a, run, 4)
    many, many_rows = _replay(authed_api_a, activity)
    assert few_rows == 7 and many_rows == 35
    assert many == few, f'{few} queries for {few_rows} cached signals, {many} for {many_rows}'
