# backend/tests/ai_pipelines/test_deal_health_freshness.py
"""
Sprint « Deal health v2 », step 8 — the freshness of a deal health (PO
decision n° 7, A13), computed AT READ TIME, never stored:

    deal_health_freshness(cycle) -> {applies, has_new_info, last_analysis_at, reasons[]}

  * applies — false for a closed cycle (DEAL_HEALTH_CLOSED_OUTCOMES) or a
    current declared step before TECHNICAL_FIT;
  * has_new_info — NO_ANALYSIS_YET (no snapshot), NEW_SOURCES (a source
    changed since the cursor, or another static-context fingerprint),
    STEP_CHANGED (the current declared step differs from the last
    snapshot's declared_step; ignored when that one is NULL, the v1 ones);
  * last_analysis_at — the last snapshot's snapshot_date, or None.
Never « stale »: « new information to analyse ».

Served beside the latest snapshot (GET .../health-snapshots/latest/ —
`freshness`), with or without a snapshot: what the Strategic tab reads.

  (a) TECHNICAL_FIT + a snapshot, then an activity's notes changed →
      NEW_SOURCES, last_analysis_at = the snapshot's date;
  (b) the same with nothing new → has_new_info false;
  (c) QUALIFICATION → applies false;
  (d) TECHNICAL_FIT, no snapshot → NO_ANALYSIS_YET, last_analysis_at None;
  (e) the declared step changed since the snapshot → STEP_CHANGED;
  (f) LOST → applies false;
  (g) a PREP_CALL run after the snapshot → NOT new (the step 1 bug);
  (h) a bounded number of queries, whatever the number of sources.
"""

import copy
import json

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from app_modules.decision_cycles.constants import CycleOutcome, PipelineStep
from app_modules.decision_cycles.models import DealHealthSnapshot, DecisionCycle

from tests.ai_pipelines.conftest import fake_provider, patch_active_provider  # noqa: F401
from tests.ai_pipelines.deal_health_fixtures import V2_DIAGNOSTIC
from tests.ai_pipelines.test_prep_call_not_an_analysis import _VALID_BRIEF
from tests.decision_cycles.conftest import (  # noqa: F401
    pytest_configure,
    _jwt_only_no_csrf,
    tenant_a_id,
    tenant_b_id,
    client_account_a,
    client_account_b,
    role_individual_a,
    role_individual_b,
    user_a,
    user_b,
    account,
    other_tenant_account,
    activity,
    contact,
    api,
    authenticate,
    authed_api_a,
    authed_api_b,
    cache_invalidation_calls,
    cycle,
    five_steps,
    planned_activity_on_step,
    completed_activity_on_step,
)


pytestmark = pytest.mark.django_db

RUN_URL = '/module-ai-pipelines/deal-health/run/'
NO_ANALYSIS_YET = 'NO_ANALYSIS_YET'
NEW_SOURCES = 'NEW_SOURCES'
STEP_CHANGED = 'STEP_CHANGED'


@pytest.fixture
def provider(patch_active_provider):
    patch_active_provider.replies['deal_health'] = json.dumps(copy.deepcopy(V2_DIAGNOSTIC))
    patch_active_provider.replies['prep_call'] = json.dumps(_VALID_BRIEF)
    return patch_active_provider


@pytest.fixture
def technical_fit(cycle, five_steps, planned_activity_on_step, completed_activity_on_step):
    """Qualification done, Technical Fit current (a planned meeting)."""
    completed_activity_on_step(five_steps[0])
    meeting = planned_activity_on_step(five_steps[1], outcome_notes='First notes.')
    return {'cycle': cycle, 'steps': five_steps, 'meeting': meeting}


def _freshness(api, cycle):
    resp = api.get(f'/decision_cycles/{cycle.id}/health-snapshots/latest/')
    assert resp.status_code == 200, resp.content
    return resp.data['freshness']


def _run(api, cycle):
    resp = api.post(RUN_URL, {'decision_cycle_id': str(cycle.id)}, format='json')
    assert resp.status_code == 201, resp.content
    return DealHealthSnapshot.objects.get(id=resp.data['data']['snapshot']['id'])


# =============================================================================
# (a) / (b) — new sources since the last snapshot
# =============================================================================

def test_a_changed_activity_notes_are_new_information(authed_api_a, technical_fit, provider):
    cycle, meeting = technical_fit['cycle'], technical_fit['meeting']
    snapshot = _run(authed_api_a, cycle)

    resp = authed_api_a.post(f'/module-activities/{meeting.id}/notes/',
                             {'outcome_notes': 'Budget owner is the COO.'}, format='json')
    assert resp.status_code == 200, resp.content
    fresh = _freshness(authed_api_a, cycle)

    assert fresh['applies'] is True
    assert fresh['has_new_info'] is True
    assert fresh['reasons'] == [NEW_SOURCES]
    assert fresh['last_analysis_at'] == snapshot.snapshot_date.isoformat()


def test_b_nothing_new_is_no_new_information(authed_api_a, technical_fit, provider):
    cycle = technical_fit['cycle']
    snapshot = _run(authed_api_a, cycle)

    fresh = _freshness(authed_api_a, cycle)

    assert fresh == {
        'applies': True, 'has_new_info': False,
        'last_analysis_at': snapshot.snapshot_date.isoformat(), 'reasons': [],
    }


# =============================================================================
# (c) / (f) — when the freshness does not apply
# =============================================================================

def test_c_a_deal_in_qualification_does_not_apply(
    authed_api_a, cycle, five_steps, planned_activity_on_step,
):
    planned_activity_on_step(five_steps[0])          # Qualification is current

    fresh = _freshness(authed_api_a, cycle)

    assert fresh['applies'] is False
    assert fresh['has_new_info'] is False


def test_f_a_lost_deal_does_not_apply(authed_api_a, technical_fit):
    cycle = technical_fit['cycle']
    DecisionCycle.objects.filter(pk=cycle.pk).update(outcome=CycleOutcome.LOST)

    fresh = _freshness(authed_api_a, cycle)

    assert fresh['applies'] is False
    assert fresh['has_new_info'] is False


# =============================================================================
# (d) — no analysis yet
# =============================================================================

def test_d_no_snapshot_is_no_analysis_yet(authed_api_a, technical_fit):
    resp = authed_api_a.get(f"/decision_cycles/{technical_fit['cycle'].id}/health-snapshots/latest/")
    assert resp.status_code == 200
    assert resp.data['data'] is None                 # one call, even without a snapshot

    fresh = resp.data['freshness']
    assert fresh['applies'] is True
    assert fresh['has_new_info'] is True
    assert fresh['reasons'] == [NO_ANALYSIS_YET]
    assert fresh['last_analysis_at'] is None


# =============================================================================
# (e) — the declared step changed since the snapshot
# =============================================================================

def test_e_the_declared_step_moved_on_since_the_snapshot(
    authed_api_a, technical_fit, provider, user_a, planned_activity_on_step,
):
    from django.utils import timezone
    from app_modules.activities.constants import ActivityStatus
    from app_modules.activities.services.next_step_materialization import current_decision_step

    cycle, steps, meeting = technical_fit['cycle'], technical_fit['steps'], technical_fit['meeting']
    _run(authed_api_a, cycle)                         # declared at TECHNICAL_FIT
    meeting.status = ActivityStatus.COMPLETED         # the Technical Fit meeting is held
    meeting.completed_at = timezone.now()
    meeting.save(user=user_a, client_id=cycle.client_id)
    planned_activity_on_step(steps[2])
    assert current_decision_step(cycle).stage == PipelineStep.SOLUTION_VALIDATION

    fresh = _freshness(authed_api_a, cycle)

    assert fresh['has_new_info'] is True
    assert STEP_CHANGED in fresh['reasons']


def test_e_the_step_alone_is_new_information(authed_api_a, technical_fit, provider):
    """Only the step differs (the snapshot was declared at Qualification)."""
    cycle = technical_fit['cycle']
    snapshot = _run(authed_api_a, cycle)
    DealHealthSnapshot.objects.filter(pk=snapshot.pk).update(
        declared_step=PipelineStep.QUALIFICATION,
    )

    fresh = _freshness(authed_api_a, cycle)

    assert fresh['has_new_info'] is True
    assert fresh['reasons'] == [STEP_CHANGED]


def test_e_a_v1_snapshot_without_declared_step_ignores_the_step(
    authed_api_a, technical_fit, provider,
):
    cycle = technical_fit['cycle']
    snapshot = _run(authed_api_a, cycle)
    DealHealthSnapshot.objects.filter(pk=snapshot.pk).update(declared_step=None)

    assert _freshness(authed_api_a, cycle)['has_new_info'] is False


# =============================================================================
# (g) — a prep-call brief analyses nothing
# =============================================================================

def test_g_a_prep_call_run_after_the_snapshot_is_not_new(
    authed_api_a, technical_fit, provider,
):
    cycle, meeting = technical_fit['cycle'], technical_fit['meeting']
    _run(authed_api_a, cycle)

    resp = authed_api_a.post('/module-ai-pipelines/prep-call/run/',
                             {'activity_id': str(meeting.id)}, format='json')
    assert resp.status_code == 201, resp.content      # the brief really ran

    fresh = _freshness(authed_api_a, cycle)
    assert fresh['has_new_info'] is False
    assert fresh['reasons'] == []


# =============================================================================
# (h) — bounded queries, no read of the transcripts
# =============================================================================

def test_h_the_number_of_queries_does_not_grow_with_the_sources(
    authed_api_a, technical_fit, provider, planned_activity_on_step,
):
    from app_modules.ai_pipelines.services.deal_health_freshness import deal_health_freshness

    cycle, steps = technical_fit['cycle'], technical_fit['steps']

    def count():
        # The worst case: NOTHING new — every check runs (none short-cuts).
        dc = DecisionCycle.objects.get(pk=cycle.pk)
        with CaptureQueriesContext(connection) as queries:
            fresh = deal_health_freshness(dc)
        assert fresh['has_new_info'] is False
        return queries

    _run(authed_api_a, cycle)
    few = count()
    for i in range(6):
        planned_activity_on_step(steps[1], transcript='x' * 5000, outcome_notes=f'Note {i}')
    _run(authed_api_a, cycle)                         # analysed: nothing new again
    many = count()

    assert len(many) == len(few), [q['sql'] for q in many.captured_queries]
    assert len(few) <= 25
    # The transcripts are never read: existence queries only on activities.
    for q in many.captured_queries:
        if 'module_activities' in q['sql'] and '"transcript"' in q['sql'].split('FROM')[0]:
            raise AssertionError(f'transcript read: {q["sql"][:200]}')
