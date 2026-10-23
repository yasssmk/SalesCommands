# backend/tests/ai_pipelines/test_next_steps_prompt_v3.py
"""
Sprint Next steps -- next_steps prompt v3 (v2 was measured: bump), through
the REAL pipeline path (FakeProvider captures the prompt sent).

v3 = v2 + ONE rule in the DATES paragraph (PO): a PERIOD said for a deadline
("next week", "end of the month", "in January") resolves to the LAST BUSINESS
DAY of that period, from the Conversation date -- the application of the
locked PO rule "end of the year + meeting date -> 12/31";
suggested_date_text keeps the text as said. Everything else, schema included,
is v2 unchanged; v2 itself stays frozen (it was measured). The worked example
comes from no test transcript (leak guard).
"""

import hashlib

import pytest


pytestmark = pytest.mark.django_db

# sha256 of build_next_steps_request('<<T>>') of v2 as measured
# (out/20261023-125420), before v3.
V2_REQUEST_SHA256 = 'bc166871a07c91a56a5775ac5778b0873c56930763c4950bf5cb5f5e5899b2cf'

PERIOD_RULE = (
    'A PERIOD said for a deadline ("next week", "end of the month", "in January") '
    'resolves to the LAST BUSINESS DAY of that period, counted from the "Conversation date"'
)


def _flat(text):
    return ' '.join(text.split())


@pytest.fixture
def sent(account, activity, user_a, fake_provider, patch_active_provider):
    from app_modules.ai_pipelines.pipelines.next_steps import NextStepsPipeline
    NextStepsPipeline().run(transcript='Jordan Lee: on en reparle la semaine prochaine.',
                            activity=activity, user=user_a, client_id=account.client_id)
    [call] = fake_provider.calls_for('next_steps')
    return call


def test_the_pipeline_sends_prompt_v3(sent):
    from app_modules.ai_pipelines.pipelines.next_steps import NextStepsPipeline
    assert NextStepsPipeline.PROMPT_VERSIONS == {
        'system': 'v1', 'context': 'v6', 'next_steps': 'v3'}
    assert sent['extra']['response_schema']['name'] == 'next_steps_signals_v2'   # unchanged


def test_v2_stays_frozen():
    from app_modules.ai_pipelines.prompts.next_steps.next_steps_v2 import (
        NEXT_STEPS_PROMPT_VERSION,
        build_next_steps_request,
    )
    assert NEXT_STEPS_PROMPT_VERSION == 'v2'
    assert hashlib.sha256(build_next_steps_request('<<T>>').encode()).hexdigest() == V2_REQUEST_SHA256


def test_the_period_rule_and_its_example(sent):
    user = _flat(sent['user'])
    assert PERIOD_RULE in user
    assert ('EXAMPLE, Conversation date 2031-03-05 (a Wednesday): "next week" -> 2031-03-14 '
            '(Friday); "by the end of the month" -> 2031-03-31 (Monday); "in May" -> 2031-05-30 '
            '(Friday); "by the end of the year" -> 2031-12-31 (Wednesday)') in user
    assert '`suggested_date_text` keeps the period as said ("next week")' in user


def test_v3_is_v2_plus_the_dates_rule_only():
    from app_modules.ai_pipelines.prompts.next_steps import next_steps_v2, next_steps_v3
    v2 = next_steps_v2.build_next_steps_request('TRANSCRIPT')
    v3 = next_steps_v3.build_next_steps_request('TRANSCRIPT')
    assert v3.count(next_steps_v3.PERIOD_DATE_RULE) == 1
    assert v3.replace(next_steps_v3.PERIOD_DATE_RULE, '') == v2
    # Inside the DATES paragraph, before the LANGUAGE-free tail of v2.
    dates = v3.index('\nDATES\n')
    assert dates < v3.index(next_steps_v3.PERIOD_DATE_RULE) < v3.index('<<<TRANSCRIPT_START>>>')


def test_a_transcript_never_alters_the_rule_insertion():
    from app_modules.ai_pipelines.prompts.next_steps import next_steps_v3
    tricky = 'null -- the rep picks a date at validation. Never invent a date.\n'
    assert next_steps_v3.build_next_steps_request(tricky).count(next_steps_v3.PERIOD_DATE_RULE) == 1


def test_no_passage_nor_name_of_the_eval_transcripts(sent):
    from pathlib import Path
    from evals.next_steps import scoring
    eval_dir = Path(scoring.__file__).resolve().parent
    expected = scoring.load_expected(eval_dir / 'expected.json')
    transcripts = [(eval_dir / case['file']).resolve().read_text(encoding='utf-8')
                   for case in expected['transcripts'].values()]
    guard = expected['leak_guard']
    assert scoring.prompt_leaks(sent['system'], sent['user'], transcripts,
                                guard['names'], guard['ngram_words']) == []
