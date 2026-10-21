# backend/tests/ai_pipelines/test_people_structured_output.py
"""
TD-279 M (PO) -- People on gpt-5.6-terra + Structured Outputs + UNKNOWN
offered, through the REAL pipeline path (FakeProvider -> persist_stage).

  * The people stage calls gpt-5.6-terra, reasoning medium, NO temperature,
    with a STRICT response schema of the current output ({"signals": [...]}):
    additionalProperties false, every field required, nullables typed
    [..., "null"], enums taken from the SAME enums as the context taxonomy
    (role WITH UNKNOWN, influence, departments).
  * Prompt v8 + context v9 offer UNKNOWN and the "never guess a role" rule.
  * An answer with role UNKNOWN is persisted UNKNOWN.
  * The 6 other stages: no schema, no extra argument (non-regression).
"""

import json

import pytest

from app_modules.ai_pipelines import config
from app_modules.signals.constants import InfluenceLevel, PeopleRole


pytestmark = pytest.mark.django_db

TERRA = 'gpt-5.6-terra'
FIELDS = {
    'full_name', 'job_title', 'role', 'influence', 'department', 'notes', 'source_quote',
    'confidence', 'is_inferred',
}
UNKNOWN_RULE = (
    'When NOTHING in the transcript establishes the person\'s role, set '
    '`role` to "UNKNOWN" -- NEVER guess a role.'
)


def _flat(text):
    return ' '.join(text.split())


def _run(account, activity, user_a, fake_provider, people=None):
    from app_modules.ai_pipelines.pipelines.transcript_signals import (
        QualificationSignalsPipeline,
    )
    if people is not None:
        fake_provider.replies = {'people': json.dumps({'signals': people})}
    return QualificationSignalsPipeline().run(
        transcript='Jordan Lee: on regarde plusieurs outils.',
        activity=activity, user=user_a, client_id=account.client_id,
    )


def _departments():
    from app_modules.core_modules.models import StandardDepartment
    return list(StandardDepartment.DepartmentChoices.values)


class TestPeopleCall:

    def test_people_calls_terra_in_reasoning_mode(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        _run(account, activity, user_a, fake_provider)
        [call] = fake_provider.calls_for('people')
        assert call['model'] == TERRA
        assert call['temperature'] is None
        assert call['extra']['reasoning_effort'] == 'medium'

    def test_people_sends_a_strict_schema_of_the_current_output(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        _run(account, activity, user_a, fake_provider)
        [call] = fake_provider.calls_for('people')
        schema = call['extra']['response_schema']
        root = schema['schema']
        assert root['additionalProperties'] is False
        assert root['required'] == ['signals']
        item = root['properties']['signals']['items']
        assert item['additionalProperties'] is False
        assert set(item['properties']) == FIELDS
        assert set(item['required']) == FIELDS
        props = item['properties']
        # Enums = the SAME enums as the context taxonomy; UNKNOWN included.
        assert props['role'] == {'type': 'string', 'enum': list(PeopleRole.values)}
        assert PeopleRole.UNKNOWN.value in props['role']['enum']
        assert props['influence'] == {
            'type': ['string', 'null'], 'enum': [*InfluenceLevel.values, None]}
        assert props['department'] == {
            'type': ['string', 'null'], 'enum': [*_departments(), None]}
        assert props['full_name'] == {'type': ['string', 'null']}
        assert props['confidence'] == {'type': 'number'}
        assert props['is_inferred'] == {'type': 'boolean'}

    def test_prompt_and_context_offer_unknown_and_the_rule(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        _run(account, activity, user_a, fake_provider)
        [call] = fake_provider.calls_for('people')
        user = _flat(call['user'])
        assert '"UNKNOWN" (Unknown)' in user           # context taxonomy
        assert UNKNOWN_RULE in user                     # request rule
        # Every enum value of the schema is listed in the context.
        props = call['extra']['response_schema']['schema']['properties'][
            'signals']['items']['properties']
        for code in props['role']['enum']:
            assert f'"{code}"' in user
        for name in _departments():
            assert f'"{name}"' in user

    def test_an_unknown_answer_is_persisted_unknown(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        signals = _run(account, activity, user_a, fake_provider, people=[{
            'full_name': 'Jordan Lee', 'role': 'UNKNOWN', 'influence': None,
            'department': None, 'notes': 'Speaks; nothing states the role.',
            'source_quote': 'on regarde plusieurs outils.',
            'confidence': 0.8, 'is_inferred': False,
        }])['signals_by_stage']['people']
        [signal] = signals
        signal.refresh_from_db()
        assert signal.role == PeopleRole.UNKNOWN
        assert signal.full_name == 'Jordan Lee'

    def test_the_other_stages_send_no_schema(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        _run(account, activity, user_a, fake_provider)
        default = config.PROVIDER_CONFIG[config.ACTIVE_PROVIDER]
        others = [c for c in fake_provider.calls if c['stage'] != 'people']
        assert len(others) == 6
        for call in others:
            assert call['extra'] == {}
            assert call['model'] == default['model']
            assert call['temperature'] == 0.0


class TestVersions:

    def test_versions(self):
        from app_modules.ai_pipelines.prompts.transcript_signals.context import (
            CONTEXT_VERSION,
        )
        from app_modules.ai_pipelines.prompts.transcript_signals.people_v1 import (
            PEOPLE_PROMPT_VERSION,
        )
        assert PEOPLE_PROMPT_VERSION == 'v9'   # v9: job_title (TD-279 D)
        assert CONTEXT_VERSION == 'v9'
