# backend/tests/ai_pipelines/test_prep_call_dh_snapshot_tenant.py
"""
Sprint 2 Game Plan — sub-step S3: the prep call reads the deal-health
snapshot of its cycle INSIDE the tenant, through the canonical reader
DealHealthEvidenceBuilder.latest_snapshot (decision_cycle AND client_id).

Before: the prep-call assembler had two readers of its own
(input_pack_assembler.py `_get_last_snapshot_date` and
`build_maturity_snapshot`), filtered on `decision_cycle` only — a snapshot
row carrying ANOTHER tenant's client_id on this cycle was read: its global
reading and dimensions went into the prompt, its date into the context.

Real path: POST /module-ai-pipelines/prep-call/run/ with the real
PrepCallPipeline (fake LLM provider, tests/ai_pipelines/conftest.py).

Seeding: the INCONSISTENT row (client_id of tenant B on the cycle of tenant
A) has no API path — no endpoint writes a snapshot with a foreign tenant —
so that row alone is seeded through the ORM. Everything else goes through
the endpoint.

Also proven: for a normal cycle, the snapshot read is the same as before
(the latest one of the tenant).

DB: Postgres.
"""

import json

import pytest

from tests.ai_pipelines.test_prep_call_not_an_analysis import _VALID_BRIEF
from tests.signals.test_signal_cycle_attachment import _cycle, _plain_activity


pytestmark = pytest.mark.django_db

RUN_URL = '/module-ai-pipelines/prep-call/run/'

OWN_OLD = 'Own older reading of the deal.'
OWN_NEW = 'Own latest reading of the deal.'
FOREIGN = 'FOREIGN TENANT reading — must never be read.'


@pytest.fixture
def prep_call_provider(patch_active_provider):
    patch_active_provider.replies['prep_call'] = json.dumps(_VALID_BRIEF)
    return patch_active_provider


@pytest.fixture
def cycle(account, user_a):
    return _cycle(account, user_a)


@pytest.fixture
def activity(account, user_a, cycle):
    a = _plain_activity(account, user_a)
    a.decision_cycle = cycle
    a.save(user=user_a, client_id=account.client_id)
    return a


def _snapshot(cycle, user, reading, status, *, client_id):
    """A deal-health snapshot on `cycle`, stamped with `client_id`."""
    from app_modules.decision_cycles.models import DealHealthSnapshot
    snap = DealHealthSnapshot(
        decision_cycle=cycle,
        diagnostic={
            'global_reading': reading,
            'dimensions': [{'key': 'urgency', 'status': status}],
        },
    )
    snap.save(user=user, client_id=client_id)
    return snap


def _run_and_prompt(api, activity, provider):
    resp = api.post(RUN_URL, {'activity_id': str(activity.id)}, format='json')
    assert resp.status_code == 201, resp.content
    prompts = [c['user'] for c in provider.calls if c['stage'] == 'prep_call']
    assert len(prompts) == 1, provider.calls  # the real pipeline ran once
    return prompts[0]


# =============================================================================
# ANOTHER TENANT'S ROW ON THIS CYCLE — never read
# =============================================================================

def test_a_foreign_tenant_snapshot_is_not_read(
    authed_api_a, activity, cycle, user_b, client_account_b, prep_call_provider,
):
    foreign = _snapshot(cycle, user_b, FOREIGN, 'contradictory',
                        client_id=client_account_b.id)

    prompt = _run_and_prompt(authed_api_a, activity, prep_call_provider)

    assert FOREIGN not in prompt
    assert 'urgency: contradictory' not in prompt
    assert foreign.snapshot_date.isoformat() not in prompt
    # No snapshot of the tenant: the « none » branch of the context.
    assert 'No deal health snapshot available' in prompt


def test_a_newer_foreign_snapshot_does_not_hide_the_tenant_one(
    authed_api_a, activity, cycle, user_a, user_b, client_account_b,
    prep_call_provider,
):
    own = _snapshot(cycle, user_a, OWN_NEW, 'confirmed', client_id=cycle.client_id)
    _snapshot(cycle, user_b, FOREIGN, 'contradictory', client_id=client_account_b.id)

    prompt = _run_and_prompt(authed_api_a, activity, prep_call_provider)

    assert FOREIGN not in prompt
    assert OWN_NEW in prompt
    assert 'urgency: confirmed' in prompt
    assert f'Last deal health snapshot: {own.snapshot_date.isoformat()}' in prompt


# =============================================================================
# NORMAL CYCLE — the snapshot read is unchanged (the latest of the tenant)
# =============================================================================

def test_the_latest_tenant_snapshot_is_read_as_before(
    authed_api_a, activity, cycle, user_a, prep_call_provider,
):
    _snapshot(cycle, user_a, OWN_OLD, 'unclear', client_id=cycle.client_id)
    latest = _snapshot(cycle, user_a, OWN_NEW, 'confirmed', client_id=cycle.client_id)

    prompt = _run_and_prompt(authed_api_a, activity, prep_call_provider)

    assert OWN_NEW in prompt
    assert OWN_OLD not in prompt
    assert 'urgency: confirmed' in prompt
    assert f'Last deal health snapshot: {latest.snapshot_date.isoformat()}' in prompt
