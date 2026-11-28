# backend/tests/ai_pipelines/test_prep_call_v2_2.py
"""
Sprint 2 Game Plan — G13f (PO decisions of 28/11, before the UI): the system
v2.2 and the outline v2.1 (v2 and v2.1 kept, unchanged).

  1. the next step is the next logical step of the client's buying process;
     the closing gets the person's agreement and locks it in during the
     meeting; no date, time, duration nor detailed content of the next
     meeting (v2's « two date options » rule is replaced); the opening
     confirms the time the person has; a message proposes to agree on a next
     exchange;
  2. readable in the middle of a meeting: each item one short line, at most
     PREP_CALL_LINE_MAX_WORDS words, opening on an action verb (the plan).

The outline schema keeps the SAME keys (no migration): a v2 snapshot stays
readable.

Real path: POST /module-ai-pipelines/prep-call/run/ (the fake provider
records the system prompt and the schema sent).

DB: Postgres.
"""

import json

import pytest

from app_modules.activities.constants import ActivityType
from app_modules.activities.models import Activity
from app_modules.ai_pipelines.constants import PREP_CALL_LINE_MAX_WORDS
from app_modules.ai_pipelines.models import AIPipelineRun, PrepCallSnapshot
from app_modules.ai_pipelines.prompts.prep_call import outline_v2, outline_v2_1, system_v2_1, system_v2_2
from app_modules.ai_pipelines.services.prep_call import rhetoric_guide

from tests.ai_pipelines.test_prep_call_activity_roster import _contact
from tests.ai_pipelines.test_prep_call_not_an_analysis import _VALID_BRIEF, _preparable_activity


pytestmark = pytest.mark.django_db

RUN_URL = '/module-ai-pipelines/prep-call/run/'


def _post(api, activity):
    resp = api.post(RUN_URL, {'activity_id': str(activity.id)}, format='json')
    assert resp.status_code == 201, resp.content
    return AIPipelineRun.objects.get(source_activity=activity)


def test_the_plan_is_generated_with_v2_2_and_the_outline_v2_1(
    authed_api_a, account, user_a, patch_active_provider,
):
    patch_active_provider.replies['prep_call'] = json.dumps(_VALID_BRIEF)

    run = _post(authed_api_a, _preparable_activity(account, user_a))

    [call] = patch_active_provider.calls_for('prep_call')
    system = call['system']
    assert rhetoric_guide.NEXT_STEP_RULE in system
    assert rhetoric_guide.OPENING_TIME_RULE in system
    assert rhetoric_guide.readability_rule(PREP_CALL_LINE_MAX_WORDS) in system
    assert f'at most {PREP_CALL_LINE_MAX_WORDS} words' in call['user']
    assert 'two date options' not in system and 'two date options' not in call['user']
    assert system_v2_1.SLOT_RULE in system                            # v2.1's rule kept
    assert call['extra']['response_schema'] == outline_v2_1.PREP_CALL_OUTLINE_SCHEMA
    assert run.prompt_versions == {'system': 'v2.3', 'context': 'v2', 'outline': 'v2.1'}   # v2.3 keeps v2.2


def test_the_message_proposes_a_next_exchange_and_is_not_bound_by_the_plan_lines(
    authed_api_a, account, user_a, patch_active_provider,
):
    email = _preparable_activity(account, user_a)
    Activity.objects.filter(pk=email.pk).update(activity_type=ActivityType.EMAIL)
    email.refresh_from_db()
    email.contacts.add(_contact(account, user_a, 'Claire', 'Morel', 'claire@client.test'))
    patch_active_provider.replies['prep_call'] = json.dumps({'messages': [
        {'ref': 'Claire', 'language': 'en', 'subject': 'Next step',
         'body': 'Hello Claire, could we agree on a next exchange?'}]})

    run = _post(authed_api_a, email)

    [call] = patch_active_provider.calls_for('prep_call')
    assert rhetoric_guide.MESSAGE_NEXT_EXCHANGE_RULE in call['system']
    assert rhetoric_guide.NEXT_STEP_RULE in call['system']
    assert rhetoric_guide.readability_rule(PREP_CALL_LINE_MAX_WORDS) not in call['system']
    assert run.prompt_versions['system'] == 'v2.3'   # v2.3 keeps v2.2


def test_the_outline_keeps_the_v2_keys_and_describes_the_closing_and_the_opening():
    def keys(schema):
        if isinstance(schema, dict):
            return {k: keys(v) for k, v in schema.items() if k not in ('description',)}
        if isinstance(schema, list):
            return [keys(v) for v in schema]
        return schema
    v2, v2_1 = outline_v2.PREP_CALL_OUTLINE_SCHEMA['schema'], outline_v2_1.PREP_CALL_OUTLINE_SCHEMA['schema']
    assert keys(v2_1) == keys(v2)                                     # no migration
    closing = v2_1['properties']['closing']['properties']
    assert 'Never a date, a time or a duration' in closing['when']['description']
    assert 'agreement' in closing['keep_control']['description']
    assert 'No invented duration' in v2_1['properties']['opening']['properties']['time']['description']


def test_v2_and_v2_1_are_kept_unchanged():
    from app_modules.ai_pipelines.prompts.prep_call import system_v2
    assert 'two date options' in system_v2.SYSTEM_PROMPT
    assert 'two date options' in system_v2_1.SYSTEM_PROMPT
    assert system_v2_1.SYSTEM_PROMPT_VERSION == 'v2.1' and system_v2_2.SYSTEM_PROMPT_VERSION == 'v2.2'
    assert outline_v2.OUTLINE_PROMPT_VERSION == 'v2' and 'two date options' in outline_v2._FIELD_RULES


def test_a_v2_snapshot_stays_readable(authed_api_a, account, user_a):
    meeting = _preparable_activity(account, user_a)
    PrepCallSnapshot(activity=meeting, brief=_VALID_BRIEF, input_hash='h' * 64, schema_version=2,
                     output_kind='PLAN').save(user=user_a, client_id=meeting.client_id)

    resp = authed_api_a.get(f'/module-ai-pipelines/prep-call/by-activity/{meeting.id}/')

    assert resp.status_code == 200
    assert resp.json()['data']['brief'] == _VALID_BRIEF
