# backend/tests/ai_pipelines/test_prep_call_nothing_new.py
"""
Sprint 2 Game Plan — sub-step G9 (defect, PO decision Q1): a Regenerate with
nothing new is an INFO, not the old brief served again.

Before: POST /module-ai-pipelines/prep-call/run/ with the same inputs as an
existing snapshot answered 201 with that OLD snapshot
(pipelines/prep_call.py dedup: any snapshot of the activity with the same
hash) — a silent « success », no new Game Plan, nothing said.

Now (the deal health's _blocked(NO_NEW_SOURCES) pattern): a generation
happens only when the inputs CHANGED since the activity's LAST Game Plan
(the dedup hash v2, G7). Otherwise: 200 + the INFO code
PREP_CALL_NOTHING_NEW (G2) with its message (core/error_messages.py) and the
last Game Plan's date — no run, no LLM call, nothing written. The very first
generation of an activity is never blocked.
The view's order: permission (403), the business rules of G3 (INFO), «
nothing new » (INFO), then the generation.

Real path: POST prep-call/run/ (real view and pipeline, fake LLM provider).

DB: Postgres.
"""

import json

import pytest
from rest_framework.test import APIClient

from app_modules.activities.constants import ActivityStatus
from app_modules.activities.models import Activity
from app_modules.ai_pipelines.constants import (
    PREP_CALL_ACTIVITY_CLOSED_CODE,
    PREP_CALL_NOTHING_NEW_CODE,
)
from app_modules.ai_pipelines.models import AIPipelineRun, PrepCallSnapshot

from tests.ai_pipelines.test_prep_call_not_an_analysis import _VALID_BRIEF, _preparable_activity


pytestmark = pytest.mark.django_db

RUN_URL = '/module-ai-pipelines/prep-call/run/'


@pytest.fixture
def provider(patch_active_provider):
    patch_active_provider.replies['prep_call'] = json.dumps(_VALID_BRIEF)
    return patch_active_provider


@pytest.fixture
def activity(account, user_a):
    return _preparable_activity(account, user_a)


def _post(api, activity):
    return api.post(RUN_URL, {'activity_id': str(activity.id)}, format='json')


def _llm_calls(provider):
    return len([c for c in provider.calls if c['stage'] == 'prep_call'])


def _runs(activity):
    return AIPipelineRun.objects.filter(source_activity=activity).count()


# =============================================================================
# THE REPRO — the same inputs twice: an INFO, nothing run
# =============================================================================

def test_a_second_identical_generation_is_an_info_without_run_nor_llm_call(
    authed_api_a, activity, provider,
):
    first = _post(authed_api_a, activity)
    assert first.status_code == 201, first.content
    snapshot = PrepCallSnapshot.objects.get(activity=activity)

    second = _post(authed_api_a, activity)

    assert second.status_code == 200, second.content
    body = second.json()
    assert body['success'] is True
    assert body['code'] == PREP_CALL_NOTHING_NEW_CODE
    assert snapshot.snapshot_date.date().isoformat() in body['message']
    assert body['data']['run'] is None and body['data']['snapshot'] is None
    assert body['data']['last_generated_at'] == snapshot.snapshot_date.isoformat()
    assert _llm_calls(provider) == 1                    # no second call
    assert _runs(activity) == 1                         # no second run
    assert PrepCallSnapshot.objects.filter(activity=activity).count() == 1


# =============================================================================
# NON-REGRESSION — a changed input regenerates; the first is never blocked
# =============================================================================

def test_a_changed_input_regenerates(authed_api_a, activity, provider):
    assert _post(authed_api_a, activity).status_code == 201
    Activity.objects.filter(pk=activity.pk).update(description='A new agenda: the pilot.')

    resp = _post(authed_api_a, activity)

    assert resp.status_code == 201, resp.content
    assert _llm_calls(provider) == 2
    assert PrepCallSnapshot.objects.filter(activity=activity).count() == 2


def test_the_first_generation_is_never_blocked(authed_api_a, activity, provider):
    resp = _post(authed_api_a, activity)

    assert resp.status_code == 201, resp.content
    assert _llm_calls(provider) == 1


def test_nothing_new_is_judged_against_the_last_game_plan(authed_api_a, activity, provider):
    """Back to an OLDER state is a change since the LAST Game Plan."""
    assert _post(authed_api_a, activity).status_code == 201           # inputs A
    Activity.objects.filter(pk=activity.pk).update(description='Agenda B.')
    assert _post(authed_api_a, activity).status_code == 201           # inputs B
    Activity.objects.filter(pk=activity.pk).update(description=activity.description)

    resp = _post(authed_api_a, activity)                              # inputs A again

    assert resp.status_code == 201, resp.content
    assert _llm_calls(provider) == 3


# =============================================================================
# THE ORDER — permission, business rules, then « nothing new »
# =============================================================================

def test_the_permission_comes_before_nothing_new(
    authed_api_a, activity, provider, authenticate, client_account_a, user_a,
):
    from end_users.models import User
    assert _post(authed_api_a, activity).status_code == 201
    stranger = User.objects.create(email='rep9-a@tenant-a.test', client_account=client_account_a,
                                   role=user_a.role, is_active=True)
    client = APIClient(enforce_csrf_checks=False)
    authenticate(client, stranger, client_account_a.id)

    assert _post(client, activity).status_code == 403


def test_a_business_rule_comes_before_nothing_new(authed_api_a, activity, provider):
    assert _post(authed_api_a, activity).status_code == 201
    Activity.objects.filter(pk=activity.pk).update(status=ActivityStatus.COMPLETED)

    resp = _post(authed_api_a, activity)

    assert resp.status_code == 200, resp.content
    assert resp.json()['code'] == PREP_CALL_ACTIVITY_CLOSED_CODE
