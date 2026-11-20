# backend/tests/ai_pipelines/test_deal_health_eval_checks.py
"""
Sprint « Deal health v2 », step 7 — the automatic checks of the deal health
evaluation (evals/deal_health/scoring.py), played on RECORDED outputs
(tests/fixtures/deal_health_eval/recorded/), and the tone of prompt v2.1.

  * the correct recorded output passes every check;
  * the faulty one (a planted last name, an invented figure, a guard-rail
    leak, a rep task in top_arguments, the wrong step, an invented customer
    reference, a rhetoric label, the planted missing info lost, a schema
    error) turns each check red;
  * prompt v2.1: the 4 tone rules (PO decision of 18/11) are in the prompt,
    the guard-rail phrases are not in its examples.
"""

import json
from pathlib import Path

import pytest

from app_modules.ai_pipelines.constants import (
    DEAL_HEALTH_GUARDRAIL_LEAK_PHRASES,
    DEAL_HEALTH_RHETORIC_LABELS,
)

from evals.deal_health import scoring


RECORDED = Path(__file__).resolve().parent.parent / 'fixtures' / 'deal_health_eval' / 'recorded'

PROMPT = (RECORDED / 'input_prompt.txt').read_text(encoding='utf-8')
GOOD = json.loads((RECORDED / 'good_output.json').read_text(encoding='utf-8'))
FAULTY = json.loads((RECORDED / 'faulty_output.json').read_text(encoding='utf-8'))
CASE = json.loads((RECORDED / 'recorded_case.json').read_text(encoding='utf-8'))


# =============================================================================
# The checks on the recorded outputs
# =============================================================================

CHECKS = {
    'schema': lambda out: scoring.schema_errors(out),
    'first_names_only': lambda out: scoring.last_names_found(
        json.dumps(out, ensure_ascii=False), CASE['planted_last_names']),
    'no_invented_number': lambda out: scoring.invented_numbers(out, PROMPT),
    'no_invented_name': lambda out: scoring.invented_names(out, PROMPT),
    'no_guardrail_leak': lambda out: scoring.guardrail_leaks(out),
    'no_rhetoric_label': lambda out: scoring.rhetoric_labels(out),
    'no_rep_task_in_top_arguments': lambda out: scoring.rep_tasks_in_top_arguments(out),
}


@pytest.mark.parametrize('check', sorted(CHECKS))
def test_the_correct_recorded_output_passes(check):
    assert CHECKS[check](GOOD) == []


@pytest.mark.parametrize('check, culprit', [
    ('schema', 'objectives'),
    ('first_names_only', 'Marchetti'),
    ('no_invented_number', '120000'),
    ('no_invented_name', 'Contoso'),
    ('no_guardrail_leak', 'not invent'),
    ('no_rhetoric_label', 'ethos'),
    ('no_rep_task_in_top_arguments', 'Build a business case for Claire'),
])
def test_the_faulty_recorded_output_turns_each_check_red(check, culprit):
    findings = CHECKS[check](FAULTY)
    assert findings, f'{check}: the fault was not caught'
    assert any(culprit.lower() in str(f).lower() for f in findings), findings


def test_the_planted_missing_info_and_the_step():
    assert scoring.missing_info_found(GOOD, CASE['missing_info']) is True
    assert scoring.missing_info_found(FAULTY, CASE['missing_info']) is False
    assert scoring.step_ok(GOOD, CASE['real_step']) is True
    assert scoring.step_ok(FAULTY, CASE['real_step']) is False


def test_the_missing_info_needs_the_right_level():
    wrong_level = json.loads(json.dumps(GOOD))
    wrong_level['missing_info'][0]['level'] = 'CONTACT'
    assert scoring.missing_info_found(wrong_level, CASE['missing_info']) is False


def test_the_prompt_never_carries_a_planted_last_name():
    assert scoring.last_names_found(PROMPT, CASE['planted_last_names']) == []


# =============================================================================
# Prompt v2.1 — the tone (PO decision of 18/11)
# =============================================================================

def _v21():
    from app_modules.ai_pipelines.prompts.deal_health import diagnostic_v2_1, system_v2_1
    request = diagnostic_v2_1.build_diagnostic_request({'cycle': {'current_step': None}})
    return system_v2_1, diagnostic_v2_1, system_v2_1.SYSTEM_PROMPT + '\n' + request


def test_the_pipeline_sends_prompt_v2_1_with_the_v2_schema():
    from app_modules.ai_pipelines.pipelines.deal_health import DealHealthPipeline
    from app_modules.ai_pipelines.prompts.deal_health import diagnostic_v2, diagnostic_v2_1

    assert DealHealthPipeline.PROMPT_VERSIONS == {
        'system': 'v2.1', 'context': 'v2', 'diagnostic': 'v2.1',
    }
    assert diagnostic_v2_1.DEAL_HEALTH_RESPONSE_SCHEMA is diagnostic_v2.DEAL_HEALTH_RESPONSE_SCHEMA


@pytest.mark.parametrize('rule, markers', [
    # 1. a strategic action plan: who, what, to obtain what (+ deadline), no script
    ('action_plan', ['WHO', 'WHAT', 'TO OBTAIN', 'deadline', 'no script', 'Game Plan']),
    # 2. top_arguments = data (need + value, per person), never a rep task
    ('arguments_are_data', ['top_arguments', 'DATA', 'never a task']),
    # 3. the guard rails stay internal
    ('guardrails_internal', ['internal', 'never mention']),
    # 4. a coach who wants to win the deal
    ('coach_tone', ['coach', 'win', 'direct']),
])
def test_prompt_v2_1_carries_the_four_tone_rules(rule, markers):
    _system, _diag, text = _v21()
    lowered = text.lower()
    missing = [m for m in markers if m.lower() not in lowered]
    assert not missing, f'{rule}: {missing}'


def test_the_examples_of_prompt_v2_1_leak_no_guard_rail_and_no_rhetoric():
    _system, diag, text = _v21()
    examples = diag.TONE_EXAMPLES
    assert examples and examples in text                       # the examples are sent
    lowered = examples.lower()
    assert [p for p in DEAL_HEALTH_GUARDRAIL_LEAK_PHRASES if p in lowered] == []
    assert [w for w in DEAL_HEALTH_RHETORIC_LABELS if w in lowered] == []
    # Its good argument example is data, not a rep task.
    assert scoring.rep_tasks_in_top_arguments(
        {'top_arguments': diag.TONE_EXAMPLE_ARGUMENTS}) == []
