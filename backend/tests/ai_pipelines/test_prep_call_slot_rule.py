# backend/tests/ai_pipelines/test_prep_call_slot_rule.py
"""
Sprint 2 Game Plan — G13d (PO decision after the evaluation): the AI never
invents a precise meeting date or time, nor claims an action (« Je vous envoie
une invitation de 30 minutes pour mardi 1er décembre à 10 h »).

The rule is in the system prompt v2.1 (prompts/prep_call/system_v2_1.py),
shared by the plan AND the message; v2 is kept unchanged. The placeholder is
a constant (PREP_CALL_SLOT_PLACEHOLDERS), given in every language.

Real path: POST /module-ai-pipelines/prep-call/run/ (fake provider records
the system prompt sent).

DB: Postgres.
"""

import json

import pytest

from app_modules.activities.constants import ActivityType
from app_modules.activities.models import Activity
from app_modules.ai_pipelines.constants import PREP_CALL_SLOT_PLACEHOLDERS
from app_modules.ai_pipelines.models import AIPipelineRun
from app_modules.ai_pipelines.prompts.prep_call import system_v2, system_v2_1

from tests.ai_pipelines.test_prep_call_activity_roster import _contact
from tests.ai_pipelines.test_prep_call_not_an_analysis import _VALID_BRIEF, _preparable_activity


pytestmark = pytest.mark.django_db

RUN_URL = '/module-ai-pipelines/prep-call/run/'


def _post(api, activity):
    resp = api.post(RUN_URL, {'activity_id': str(activity.id)}, format='json')
    assert resp.status_code == 201, resp.content
    return AIPipelineRun.objects.get(source_activity=activity)


def test_the_plan_is_generated_with_the_slot_rule(authed_api_a, account, user_a, patch_active_provider):
    patch_active_provider.replies['prep_call'] = json.dumps(_VALID_BRIEF)
    meeting = _preparable_activity(account, user_a)

    run = _post(authed_api_a, meeting)

    [call] = patch_active_provider.calls_for('prep_call')
    assert system_v2_1.SLOT_RULE in call['system']
    assert run.prompt_versions['system'] == 'v2.1'


def test_the_message_is_generated_with_the_slot_rule(authed_api_a, account, user_a, patch_active_provider):
    email = _preparable_activity(account, user_a)
    Activity.objects.filter(pk=email.pk).update(activity_type=ActivityType.EMAIL)
    email.refresh_from_db()
    email.contacts.add(_contact(account, user_a, 'Claire', 'Morel', 'claire@client.test'))
    patch_active_provider.replies['prep_call'] = json.dumps({'messages': [
        {'ref': 'Claire', 'language': 'en', 'subject': 'Next step',
         'body': 'Hello Claire, would Tuesday or Wednesday work?'}]})

    run = _post(authed_api_a, email)

    [call] = patch_active_provider.calls_for('prep_call')
    assert system_v2_1.SLOT_RULE in call['system']
    assert run.prompt_versions['system'] == 'v2.1'


def test_the_rule_gives_the_placeholder_in_every_language():
    for language, label in PREP_CALL_SLOT_PLACEHOLDERS.items():
        assert f'{language} {label}' in system_v2_1.SLOT_RULE
    assert 'Tuesday or Wednesday?' in system_v2_1.SLOT_RULE          # the open window
    assert 'A meeting duration is fine' in system_v2_1.SLOT_RULE


def test_v2_1_is_v2_plus_the_slot_rule_only():
    assert system_v2_1.SLOT_RULE not in system_v2.SYSTEM_PROMPT     # v2 kept unchanged
    for v2, v2_1 in ((system_v2.SYSTEM_PROMPT, system_v2_1.SYSTEM_PROMPT),
                     (system_v2.MESSAGE_SYSTEM_PROMPT, system_v2_1.MESSAGE_SYSTEM_PROMPT)):
        assert system_v2_1.SLOT_RULE in v2_1
        for rule in system_v2._RULES:
            assert rule in v2_1
