# backend/tests/ai_pipelines/test_next_steps_prompt_v2.py
"""
Sprint Next steps 3.3 -- next_steps prompt v2 + extended strict schema,
through the REAL pipeline path (FakeProvider captures the prompt and the
schema sent).

Rules (PO):
  a) ONE distinct action = ONE next step (preparing != meeting; a first
     version != the final version);
  b) relative dates: the shared RELATIVE_DATE_RULE (date_rules.py) + the
     source text in suggested_date_text;
  c) a step INTERNAL to the prospect -> TASK carried_by_prospect=true with
     the stated deadline, PLUS a seller follow-up (CALL when explicitly said,
     else a TASK "follow up on ...");
  d) fields: DC step (a ref of the context, else null -- chosen from the
     CONTENT of the action, using the `conversation` / `current` marks), the
     prospect names as written, the internal names, the topics, the success
     criterion (only when said or deducible from what is said, else "");
  e) the model never chooses an activity to link (server ranking, 2.3).
No example from the eval transcripts (leak guard).
"""

import json

import pytest

from app_modules.activities.constants import ActivityType


pytestmark = pytest.mark.django_db

TRANSCRIPT = 'Jordan Lee: on se revoit après la revue.'
V2_FIELDS = {
    'suggested_title', 'suggested_activity_type', 'carried_by_prospect',
    'suggested_due_date', 'suggested_date_text', 'suggested_decision_step',
    'suggested_people_names', 'suggested_internal_names', 'suggested_objective',
    'suggested_success_criterion', 'suggested_topics', 'source_quote',
    'confidence', 'is_inferred',
}


def _flat(text):
    return ' '.join(text.split())


@pytest.fixture
def sent(account, activity, user_a, fake_provider, patch_active_provider):
    from app_modules.ai_pipelines.pipelines.next_steps import NextStepsPipeline
    NextStepsPipeline().run(transcript=TRANSCRIPT, activity=activity, user=user_a,
                            client_id=account.client_id)
    [call] = fake_provider.calls_for('next_steps')
    return call


class TestVersionsAndSchema:

    def test_the_pipeline_sends_prompt_v2(self):
        from app_modules.ai_pipelines.pipelines.next_steps import NextStepsPipeline
        assert NextStepsPipeline.PROMPT_VERSIONS == {
            'system': 'v1', 'context': 'v6', 'next_steps': 'v2'}

    def test_the_v1_module_is_kept_unchanged(self):
        from app_modules.ai_pipelines.prompts.next_steps.next_steps_v1 import (
            NEXT_STEPS_PROMPT_VERSION,
        )
        assert NEXT_STEPS_PROMPT_VERSION == 'v1'

    def test_a_strict_schema_of_the_v2_output(self, sent):
        schema = sent['extra']['response_schema']
        assert schema['name'] == 'next_steps_signals_v2'
        item = schema['schema']['properties']['signals']['items']
        assert item['additionalProperties'] is False
        assert set(item['properties']) == V2_FIELDS
        assert set(item['required']) == V2_FIELDS
        props = item['properties']
        assert props['suggested_activity_type'] == {
            'type': 'string', 'enum': list(ActivityType.values)}
        assert props['carried_by_prospect'] == {'type': 'boolean'}
        assert props['suggested_due_date'] == {'type': ['string', 'null']}
        assert props['suggested_decision_step'] == {'type': ['string', 'null']}
        for names in ('suggested_people_names', 'suggested_internal_names'):
            assert props[names] == {'type': 'array', 'items': {'type': 'string'}}
        for text in ('suggested_date_text', 'suggested_topics', 'suggested_success_criterion'):
            assert props[text] == {'type': 'string'}

    def test_every_schema_field_is_described_in_the_prompt(self, sent):
        for field in V2_FIELDS:
            assert f'"{field}":' in sent['user']


class TestRules:

    def test_a_one_distinct_action_one_next_step(self, sent):
        user = _flat(sent['user'])
        assert 'ONE distinct action = ONE next step' in user
        assert 'Preparing something and meeting about it are two next steps' in user
        assert 'a first version and the final version are two next steps' in user

    def test_b_relative_dates_reuse_the_shared_rule_and_keep_the_text(self, sent):
        from app_modules.ai_pipelines.prompts.transcript_signals.date_rules import (
            RELATIVE_DATE_RULE,
        )
        assert RELATIVE_DATE_RULE in sent['user']
        assert '`suggested_date_text` is the date AS SAID in the transcript' in _flat(sent['user'])

    def test_c_internal_prospect_step_plus_seller_follow_up(self, sent):
        user = _flat(sent['user'])
        assert ('A step of the PROSPECT\'s own internal process -> a TASK with '
                '`carried_by_prospect`: true') in user
        assert 'PLUS a seller follow-up' in user
        assert 'a CALL only when the transcript explicitly plans that call' in user

    def test_d_step_from_the_content_of_the_action(self, sent):
        user = _flat(sent['user'])
        assert 'chosen from the CONTENT of the action' in user
        assert '"conversation"' in user and '"current"' in user
        assert 'null when no step clearly matches' in user

    def test_d_success_criterion_only_when_said_or_deducible(self, sent):
        assert ('ONLY when it is said, or deducible from what is said; otherwise ""'
                in _flat(sent['user']))

    def test_e_the_model_never_chooses_an_activity_to_link(self, sent):
        assert 'NEVER choose, name or reference an existing activity to link' in _flat(sent['user'])

    def test_the_justification_contract_is_kept(self, sent):
        user = _flat(sent['user'])
        assert 'JUSTIFICATION' in user and 'EVIDENCE' in user and 'NOT a verbatim' in user
        assert 'INCORRECT' in user


class TestNoTestTranscriptExample:
    """Point 7 of 3.0: the leak guard of the eval on the v2 prompt."""

    def test_no_passage_nor_name_of_the_eval_transcripts(self, sent):
        from evals.next_steps import scoring
        from pathlib import Path
        eval_dir = Path(scoring.__file__).resolve().parent
        expected = scoring.load_expected(eval_dir / 'expected.json')
        transcripts = [(eval_dir / case['file']).resolve().read_text(encoding='utf-8')
                       for case in expected['transcripts'].values()]
        guard = expected['leak_guard']
        assert scoring.prompt_leaks(sent['system'], sent['user'], transcripts,
                                    guard['names'], guard['ngram_words']) == []


def test_an_answer_with_the_v2_fields_is_still_persisted(
    account, activity, user_a, fake_provider, patch_active_provider,
):
    from app_modules.ai_pipelines.pipelines.next_steps import NextStepsPipeline
    fake_provider.replies = {'next_steps': json.dumps({'signals': [{
        'suggested_title': 'Relire la revue', 'suggested_activity_type': 'TASK',
        'carried_by_prospect': False, 'suggested_due_date': None, 'suggested_date_text': '',
        'suggested_decision_step': None, 'suggested_people_names': ['Jordan Lee'],
        'suggested_internal_names': [], 'suggested_objective': '', 'suggested_success_criterion': '',
        'suggested_topics': '', 'source_quote': 'on se revoit après la revue.',
        'confidence': 0.9, 'is_inferred': False,
    }]})}
    [signal] = NextStepsPipeline().run(transcript=TRANSCRIPT, activity=activity, user=user_a,
                                       client_id=account.client_id)['signals']
    assert signal.suggested_title == 'Relire la revue'
