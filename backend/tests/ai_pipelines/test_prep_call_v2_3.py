# backend/tests/ai_pipelines/test_prep_call_v2_3.py
"""
Sprint 2 Game Plan — G13g (PO decision of 28/11 on the rhetoric): the system
v2.3 (v2.2 kept, unchanged).

ethos / pathos / logos are INTERNAL: v2.3 makes the frame explicit as a
REASONING tool — per participant and per section, the right lever (ethos =
credibility from the input's proof only; pathos, measured = what the client
expressed; logos = the input's facts and figures only), BAC, the pivots to
adapt, the adjustments to the deal, one dominant lever per section. The
OUTPUT is plain sales language (no theory name, no jargon), said as is in the
meeting. Every v2.2 rule stays. The schema does not change.

Real path: POST /module-ai-pipelines/prep-call/run/ (the fake provider
records the system prompt and the schema sent).

DB: Postgres.
"""

import json

import pytest

from app_modules.activities.constants import ActivityType
from app_modules.activities.models import Activity
from app_modules.ai_pipelines.constants import PREP_CALL_LINE_MAX_WORDS
from app_modules.ai_pipelines.models import AIPipelineRun
from app_modules.ai_pipelines.prompts.prep_call import outline_v2_1, system_v2_1, system_v2_2, system_v2_3
from app_modules.ai_pipelines.services.prep_call import rhetoric_guide as guide

from tests.ai_pipelines.test_prep_call_activity_roster import _contact
from tests.ai_pipelines.test_prep_call_not_an_analysis import _VALID_BRIEF, _preparable_activity


pytestmark = pytest.mark.django_db

RUN_URL = '/module-ai-pipelines/prep-call/run/'


def _post(api, activity):
    resp = api.post(RUN_URL, {'activity_id': str(activity.id)}, format='json')
    assert resp.status_code == 201, resp.content
    return AIPipelineRun.objects.get(source_activity=activity)


def _email(account, user_a):
    email = _preparable_activity(account, user_a)
    Activity.objects.filter(pk=email.pk).update(activity_type=ActivityType.EMAIL)
    email.refresh_from_db()
    email.contacts.add(_contact(account, user_a, 'Claire', 'Morel', 'claire@client.test'))
    return email


def _assert_the_frame_and_plain_language(system):
    assert system_v2_3.REASONING_FRAME in system
    for lever in guide.RHETORIC_LEVERS:
        assert lever in system
    for pivot in (*guide.RHETORIC_PIVOTS, *guide.RHETORIC_ADJUSTMENTS):
        assert pivot in system
    assert guide.RHETORIC_MIX in system
    assert guide.PLAIN_LANGUAGE_RULE in system
    assert 'never write it' in system                                 # the frame is internal
    assert 'HOW YOU CONVINCE:' not in system                           # v2's block, replaced


def test_the_plan_reasons_with_the_frame_and_keeps_every_v2_2_rule(
    authed_api_a, account, user_a, patch_active_provider,
):
    patch_active_provider.replies['prep_call'] = json.dumps(_VALID_BRIEF)

    run = _post(authed_api_a, _preparable_activity(account, user_a))

    [call] = patch_active_provider.calls_for('prep_call')
    system = call['system']
    _assert_the_frame_and_plain_language(system)
    for rule in system_v2_2._PLAN_RULES:                              # v2.2 kept, rule by rule
        assert rule in system
    assert guide.readability_rule(PREP_CALL_LINE_MAX_WORDS) in system
    assert system_v2_1.SLOT_RULE in system
    assert call['extra']['response_schema'] == outline_v2_1.PREP_CALL_OUTLINE_SCHEMA   # schema unchanged
    assert run.prompt_versions == {'system': 'v2.3', 'context': 'v2', 'outline': 'v2.1'}


def test_the_message_reasons_with_the_same_frame(authed_api_a, account, user_a, patch_active_provider):
    patch_active_provider.replies['prep_call'] = json.dumps({'messages': [
        {'ref': 'Claire', 'language': 'en', 'subject': 'Next step',
         'body': 'Hello Claire, could we agree on a next exchange?'}]})

    run = _post(authed_api_a, _email(account, user_a))

    [call] = patch_active_provider.calls_for('prep_call')
    _assert_the_frame_and_plain_language(call['system'])
    for rule in system_v2_2._MESSAGE_RULES:
        assert rule in call['system']
    assert guide.readability_rule(PREP_CALL_LINE_MAX_WORDS) not in call['system']
    assert run.prompt_versions['system'] == 'v2.3'


def test_the_levers_lean_on_the_input_only():
    ethos, pathos, logos, bac = guide.RHETORIC_LEVERS
    assert ethos.startswith('ETHOS') and 'from the input ONLY' in ethos
    assert pathos.startswith('PATHOS, measured') and 'never forced' in pathos
    assert logos.startswith('LOGOS') and 'figures of the input ONLY' in logos
    assert bac.startswith('BAC') and 'a capability of the input only' in bac
    assert 'never follow them to the letter' in system_v2_3.REASONING_FRAME


def test_v2_2_is_kept_unchanged():
    assert system_v2_2.SYSTEM_PROMPT_VERSION == 'v2.2' and system_v2_3.SYSTEM_PROMPT_VERSION == 'v2.3'
    assert 'HOW YOU CONVINCE:' in system_v2_2.SYSTEM_PROMPT
    assert system_v2_3.REASONING_FRAME not in system_v2_2.SYSTEM_PROMPT
    assert guide.PLAIN_LANGUAGE_RULE not in system_v2_2.SYSTEM_PROMPT
