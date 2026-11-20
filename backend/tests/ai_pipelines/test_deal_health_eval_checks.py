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
# 7b: the correct output, its names in the English possessive (straight and
# typographic apostrophes) — not an invented name.
POSSESSIVE = json.loads((RECORDED / 'possessive_output.json').read_text(encoding='utf-8'))
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


@pytest.mark.parametrize('check', sorted(CHECKS))
def test_a_possessive_is_not_an_invented_name(check):
    # « Hugo's », « Claire’s »: the possessive is removed before comparing.
    assert CHECKS[check](POSSESSIVE) == []


def test_a_real_invented_name_still_fails_beside_a_possessive():
    mixed = json.loads(json.dumps(POSSESSIVE))
    mixed['credibility']['assessment'] = "Use Contoso’s logistics reference."
    assert scoring.invented_names(mixed, PROMPT) == ['Contoso']     # reported without its possessive


def test_the_planted_missing_info_accepts_the_alternatives_of_the_grid():
    # 7b: a planted gap may be legitimately read at two levels (the clarified
    # grid): a company constraint at BUSINESS, or the tool's integration
    # requirements at DEPARTMENT — `missing_info` may list both.
    alternatives = [{'level': 'BUSINESS', 'any_of': ['security']},
                    {'level': 'DEPARTMENT', 'any_of': ['integration']}]
    department = json.loads(json.dumps(GOOD))
    department['missing_info'] = [{'level': 'DEPARTMENT', 'item': 'Integration requirements of the tool',
                                   'why_it_matters': 'x', 'suggested_question': 'x'}]
    assert scoring.missing_info_found(department, alternatives) is True
    assert scoring.missing_info_found(department, alternatives[0]) is False
    assert scoring.missing_info_found(FAULTY, alternatives) is False


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

def _sent():
    """The prompt the PIPELINE sends (whatever its version): its system prompt,
    its request module (examples) and the rendered text."""
    import importlib
    from app_modules.ai_pipelines.pipelines import deal_health as pipeline_module
    diag = importlib.import_module(pipeline_module.build_diagnostic_request.__module__)
    request = pipeline_module.build_diagnostic_request({'cycle': {'current_step': None}})
    return pipeline_module, diag, pipeline_module.SYSTEM_PROMPT + '\n' + request


def test_the_pipeline_sends_prompt_v2_2_with_the_v2_schema():
    from app_modules.ai_pipelines.pipelines.deal_health import DealHealthPipeline
    from app_modules.ai_pipelines.prompts.deal_health import diagnostic_v2

    _pipeline, diag, _text = _sent()
    # 7b: only the request layer changes (grid levels, summary structure).
    assert DealHealthPipeline.PROMPT_VERSIONS == {
        'system': 'v2.1', 'context': 'v2', 'diagnostic': 'v2.2',
    }
    assert diag.DIAGNOSTIC_PROMPT_VERSION == 'v2.2'
    assert diag.DEAL_HEALTH_RESPONSE_SCHEMA is diagnostic_v2.DEAL_HEALTH_RESPONSE_SCHEMA


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
def test_the_sent_prompt_carries_the_four_tone_rules(rule, markers):
    _pipeline, _diag, text = _sent()
    lowered = text.lower()
    missing = [m for m in markers if m.lower() not in lowered]
    assert not missing, f'{rule}: {missing}'


def test_the_examples_of_the_sent_prompt_leak_no_guard_rail_and_no_rhetoric():
    _pipeline, diag, text = _sent()
    examples = diag.TONE_EXAMPLES
    assert examples and examples in text                       # the examples are sent
    lowered = examples.lower()
    assert [p for p in DEAL_HEALTH_GUARDRAIL_LEAK_PHRASES if p in lowered] == []
    assert [w for w in DEAL_HEALTH_RHETORIC_LABELS if w in lowered] == []
    # Its good argument example is data, not a rep task.
    assert scoring.rep_tasks_in_top_arguments(
        {'top_arguments': diag.TONE_EXAMPLE_ARGUMENTS}) == []


# =============================================================================
# Prompt v2.2 (7b) — the levels of the grid, the summary structure
# =============================================================================

@pytest.mark.parametrize('rule, markers', [
    # A company constraint = BUSINESS; a department's evaluation criteria = DEPARTMENT.
    ('levels', ['company constraint', 'security policy', 'data hosting', 'compliance',
                'mandatory security review', 'BUSINESS', 'evaluation criteria',
                'integration requirements', "IT team's criteria", 'DEPARTMENT']),
    # The summary: What is won / What blocks / What comes next, short sentences.
    ('summary_structure', ['What is won', 'What blocks', 'What comes next',
                           'short sentences', 'win the deal']),
])
def test_prompt_v2_2_carries_the_clarified_levels_and_the_summary_structure(rule, markers):
    _pipeline, _diag, text = _sent()
    missing = [m for m in markers if m.lower() not in text.lower()]
    assert not missing, f'{rule}: {missing}'


def test_the_grid_no_longer_files_integration_under_business():
    _pipeline, diag, _text = _sent()
    technical_fit = next(line for line in diag._GRID.split('TECHNICAL_FIT')[1].split('\n')
                         if 'BUSINESS:' in line or 'goal' in line)
    business = diag._GRID.split('TECHNICAL_FIT')[1].split('DEPARTMENT:')[0]
    assert 'integration' not in business.split('BUSINESS:')[1].lower(), technical_fit
