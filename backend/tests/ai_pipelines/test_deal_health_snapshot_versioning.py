# backend/tests/ai_pipelines/test_deal_health_snapshot_versioning.py
"""
Sprint « Deal health v2 », step 2 — the DealHealthSnapshot is versioned.

Each snapshot records what it was produced FROM: its schema version, the
cycle's DECLARED step (the derived current step, computed ONCE through
activities/services/next_step_materialization.decision_steps_state) and the
pipeline's prompt versions. estimated_step / sources_cursor stay empty until
steps 3b / 5.

Real path only: POST /module-ai-pipelines/deal-health/run/ with the real
DealHealthPipeline (fake LLM provider, tests/ai_pipelines/conftest.py), then
GET /decision_cycles/{id}/health-snapshots/latest/.
"""

import json

import pytest

from app_modules.ai_pipelines.pipelines.deal_health import DealHealthPipeline
from app_modules.ai_pipelines.services.deal_health_evidence_builder import (
    DealHealthEvidenceBuilder,
)
from app_modules.decision_cycles.constants import DEAL_HEALTH_SCHEMA_V1, PipelineStep

from tests.ai_pipelines.test_deal_health_pipeline import _VALID_DIAGNOSTIC
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

# The keys DealHealthView and the prep call read off a snapshot / its
# diagnostic before step 2 — they must still be served.
_V1_SNAPSHOT_KEYS = {'id', 'decision_cycle', 'diagnostic', 'snapshot_date', 'pipeline_run'}
_V1_DIAGNOSTIC_KEYS = {'global_reading', 'dimensions', 'discovery_gaps', 'levers', 'themes'}


def _latest_url(cycle_id):
    return f'/decision_cycles/{cycle_id}/health-snapshots/latest/'


@pytest.fixture
def deal_health_provider(patch_active_provider):
    patch_active_provider.replies['deal_health'] = json.dumps(_VALID_DIAGNOSTIC)
    return patch_active_provider


@pytest.fixture
def technical_fit_cycle(cycle, five_steps, planned_activity_on_step, completed_activity_on_step):
    """Qualification done + an activity planned on Technical fit → the
    derived current step is TECHNICAL_FIT (tests/decision_cycles/
    test_is_current_derived.py)."""
    completed_activity_on_step(five_steps[0])
    planned_activity_on_step(five_steps[1])
    return cycle


def _run(api, cycle):
    resp = api.post(RUN_URL, {'decision_cycle_id': str(cycle.id)}, format='json')
    assert resp.status_code == 201, resp.content
    return resp.data['data']['snapshot']


def test_the_snapshot_records_the_declared_step_and_its_versions(
    authed_api_a, technical_fit_cycle, deal_health_provider,
):
    snapshot = _run(authed_api_a, technical_fit_cycle)
    assert len(deal_health_provider.calls_for('deal_health')) == 1

    latest = authed_api_a.get(_latest_url(technical_fit_cycle.id))
    assert latest.status_code == 200, latest.content

    for served in (snapshot, latest.json()['data']):
        assert served['declared_step'] == PipelineStep.TECHNICAL_FIT
        assert served['schema_version'] == DEAL_HEALTH_SCHEMA_V1
        assert served['prompt_versions'] == DealHealthPipeline.PROMPT_VERSIONS
        assert served['prompt_versions']                      # non-empty
        # Filled at steps 3b / 5 — empty here.
        assert served['estimated_step'] is None
        assert served['estimated_step_reason'] == ''
        assert served['sources_cursor'] == {}


def test_a_cycle_without_steps_has_no_declared_step(authed_api_a, cycle, deal_health_provider):
    snapshot = _run(authed_api_a, cycle)
    assert snapshot['declared_step'] is None
    assert snapshot['prompt_versions'] == DealHealthPipeline.PROMPT_VERSIONS


def test_dealhealthview_still_receives_its_keys(authed_api_a, technical_fit_cycle, deal_health_provider):
    _run(authed_api_a, technical_fit_cycle)

    latest = authed_api_a.get(_latest_url(technical_fit_cycle.id)).json()['data']
    history = authed_api_a.get(
        f'/decision_cycles/{technical_fit_cycle.id}/health-snapshots/'
    ).json()['data']

    assert _V1_SNAPSHOT_KEYS <= set(latest)
    assert _V1_DIAGNOSTIC_KEYS <= set(latest['diagnostic'])
    assert _V1_SNAPSHOT_KEYS <= set(history[0])
    assert history[0]['declared_step'] == PipelineStep.TECHNICAL_FIT


# =============================================================================
# CONTROL — the single derivation matches the former is_current loop
# =============================================================================

def _former_is_current_loop(dc):
    """The former DealHealthEvidenceBuilder._find_current_step (one
    is_current per step)."""
    for step in dc.steps.select_related('previous_step').order_by('order'):
        if step.is_current:
            return step
    return None


@pytest.mark.parametrize('done, planned', [
    ((), ()),          # fresh cycle → QUALIFICATION
    ((0,), (1,)),      # → TECHNICAL_FIT
    ((0, 1), (2,)),    # → SOLUTION_VALIDATION
    ((0, 1, 2, 3, 4), ()),  # all done, nothing planned → the STALLED tail
])
def test_current_step_is_the_same_as_the_former_loop(
    cycle, five_steps, planned_activity_on_step, completed_activity_on_step, done, planned,
):
    for i in done:
        completed_activity_on_step(five_steps[i])
    for i in planned:
        planned_activity_on_step(five_steps[i])

    expected = _former_is_current_loop(cycle)
    pack_step = DealHealthEvidenceBuilder().build(cycle)['cycle']['current_step']

    assert expected is not None
    assert pack_step['name'] == expected.name
    assert pack_step['stage'] == expected.stage
    assert pack_step['goal'] == (expected.goal or '')
    assert pack_step['criterias'] == (expected.criterias or [])
    assert pack_step['metrics'] == (expected.metrics or [])
