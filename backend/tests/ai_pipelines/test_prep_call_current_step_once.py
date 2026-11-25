# backend/tests/ai_pipelines/test_prep_call_current_step_once.py
"""
Sprint 2 Game Plan — sub-step S5 (defect): the prep call derives the cycle's
current step ONCE.

Before: PrepInputPackAssembler._find_current_step looped over the cycle's
steps and asked `step.is_current` of each (input_pack_assembler.py:147-157).
DecisionStep.is_current re-reads and re-derives the WHOLE cycle on every
call (decision_cycles/models.py:548-579): one derivation per step up to the
current one — 6 queries on `decision_steps` (34 in all) for a 5-step cycle
whose current step is the last.

Now: current_decision_step (activities/services/next_step_materialization.py
:197-202 — the shared definition of is_current, also used by the deal
health's evidence builder) derives the cycle once: 1 query on
`decision_steps`, 25 in all for the same POST.

Real path: POST /module-ai-pipelines/prep-call/run/ with the real
PrepCallPipeline (fake LLM provider). The step found is the same as before:
for every position of the current step, and for a cycle without steps,
the step in the prompt is the one the old loop (is_current per step) finds
on the same data.

DB: Postgres.
"""

import json

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from tests.ai_pipelines.conftest import fake_provider, patch_active_provider  # noqa: F401
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

RUN_URL = '/module-ai-pipelines/prep-call/run/'
# Measured on the real POST (5-step cycle, the 5th step current): 34 queries
# with the is_current loop, 25 with the single derivation.
MAX_QUERIES = 25
_CURRENT_PREFIX = 'Current step: '


@pytest.fixture
def provider(patch_active_provider):
    patch_active_provider.replies['prep_call'] = json.dumps(_VALID_BRIEF)
    return patch_active_provider


def _old_current_step(cycle):
    """The step the OLD loop found on the same data (the reference)."""
    steps = cycle.steps.select_related('previous_step').order_by('order')
    return next((s for s in steps if s.is_current), None)


def _current_step_in_prompt(provider):
    prompts = [c['user'] for c in provider.calls if c['stage'] == 'prep_call']
    assert len(prompts) == 1, provider.calls  # the real pipeline ran once
    lines = [l for l in prompts[0].splitlines() if l.startswith(_CURRENT_PREFIX)]
    assert len(lines) <= 1, lines
    return lines[0][len(_CURRENT_PREFIX):] if lines else None


def _post(api, activity):
    resp = api.post(RUN_URL, {'activity_id': str(activity.id)}, format='json')
    assert resp.status_code == 201, resp.content
    return resp


def _step_queries(ctx):
    return [q['sql'] for q in ctx.captured_queries if '"decision_steps"' in q['sql']]


def _make_current(index, five_steps, completed_activity_on_step, planned_activity_on_step):
    """Steps before `index` done, a planned activity on `index`: the step at
    `index` is the current one. Returns the activity to prepare."""
    for step in five_steps[:index]:
        completed_activity_on_step(step)
    return planned_activity_on_step(five_steps[index])


# =============================================================================
# THE REPRO — one derivation, whatever the number of steps
# =============================================================================

def test_the_current_step_is_derived_once(
    authed_api_a, cycle, five_steps, completed_activity_on_step,
    planned_activity_on_step, provider, django_assert_max_num_queries,
):
    target = _make_current(4, five_steps, completed_activity_on_step,
                           planned_activity_on_step)

    with django_assert_max_num_queries(MAX_QUERIES):
        with CaptureQueriesContext(connection) as ctx:
            _post(authed_api_a, target)

    assert len(_step_queries(ctx)) == 1, _step_queries(ctx)
    # The same step as before.
    assert _old_current_step(cycle).name == five_steps[4].name
    assert _current_step_in_prompt(provider) == five_steps[4].name


# =============================================================================
# THE SAME STEP AS BEFORE — every position, and no step at all
# =============================================================================

@pytest.mark.parametrize('index', [0, 1, 2, 3, 4])
def test_the_step_found_is_the_one_the_old_loop_found(
    index, authed_api_a, cycle, five_steps, completed_activity_on_step,
    planned_activity_on_step, provider,
):
    target = _make_current(index, five_steps, completed_activity_on_step,
                           planned_activity_on_step)
    reference = _old_current_step(cycle)

    _post(authed_api_a, target)

    assert reference is not None
    assert reference.name == five_steps[index].name
    assert _current_step_in_prompt(provider) == reference.name


def test_a_cycle_without_steps_has_no_current_step_as_before(
    authed_api_a, account, user_a, cycle, provider,
):
    from app_modules.activities.constants import ActivityStatus, ActivityType
    from app_modules.activities.models import Activity
    target = Activity(title='Planned call', activity_type=ActivityType.CALL,
                      status=ActivityStatus.PLANNED, account=account, owner=user_a,
                      decision_cycle=cycle)
    target.save(user=user_a, client_id=account.client_id)
    assert _old_current_step(cycle) is None

    _post(authed_api_a, target)

    assert _current_step_in_prompt(provider) is None
