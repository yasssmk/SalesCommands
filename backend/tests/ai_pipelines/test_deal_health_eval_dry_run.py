# backend/tests/ai_pipelines/test_deal_health_eval_dry_run.py
"""
Sprint « Deal health v2 », step 7 — the evaluation tool end to end, OFFLINE:
evals/deal_health/run_deal_health_eval.py --dry-run seeds the 5 fictitious
cases (the standard creation paths), runs the REAL DealHealthPipeline on
every cell of the format x model matrix with a spy provider (no network),
scores each recorded call and writes the side-by-side report. Everything it
created is rolled back.
"""

import json

import pytest

from app_modules.ai_pipelines.constants import DEAL_HEALTH_INPUT_FORMAT_JSON

from evals.deal_health import run_deal_health_eval as tool
from evals.deal_health import scoring


pytestmark = pytest.mark.django_db


@pytest.fixture
def dry_run(tmp_path):
    out_dir = tool.main(['--dry-run', '--out', str(tmp_path / 'run')])
    records = list(tool.load_records(out_dir, sorted(p.name for p in out_dir.iterdir() if p.is_dir())))
    return out_dir, records


def test_the_dry_run_plays_the_whole_matrix_and_writes_the_report(dry_run):
    out_dir, records = dry_run

    # 5 cases x 2 formats x 2 models (X, Y) x n=1.
    assert len(tool.CASES) == 5
    assert len(records) == 20
    assert {(r['format'], r['provider_key']) for r in records} == {
        ('sections', 'openai_deal_health'), ('sections', 'openai_deal_health_challenger'),
        ('json', 'openai_deal_health'), ('json', 'openai_deal_health_challenger'),
    }
    assert all(r['error'] is None for r in records), [r['error'] for r in records if r['error']]
    assert all(r['prompt_versions'] == {'system': 'v2.1', 'context': 'v2', 'diagnostic': 'v2.1'}
               for r in records)

    report = (out_dir / 'report.md').read_text(encoding='utf-8')
    for case in tool.CASES:
        assert f'## Cas `{case}`' in report
    assert '## Récapitulatif' in report and '## Plafonds et délai' in report
    assert (out_dir / 'summary.csv').exists() and (out_dir / 'summary.md').exists()


def test_the_dry_run_prompts_carry_first_names_only_and_both_formats(dry_run):
    _out_dir, records = dry_run
    prompts = {}
    for record in records:
        assert record['metrics']['last_names_in_prompt'] == [], record['variant']
        prompts[(record['case'], record['format'], record['provider_key'])] = record['attempts'][0]['user']
    for case in tool.CASES:
        sections = prompts[(case, 'sections', 'openai_deal_health')]
        whole = prompts[(case, 'json', 'openai_deal_health')]
        expected = tool._expected(case)
        # The people DO reach the prompt — by first name (non-vacuity of the
        # « no last name » check).
        assert expected['decision_maker'] in sections and expected['decision_maker'] in whole
        assert sections != whole                       # format A != format B
        assert whole.count('"stakeholders":') == 1     # B: the whole view as one JSON


def test_the_checks_run_on_every_call_and_catch_the_planted_faults(dry_run):
    _out_dir, records = dry_run
    for record in records:
        checks = scoring.checks(record['metrics'])
        faulty = (record['case'] == 'qualification_sparse'
                  and record['format'] == DEAL_HEALTH_INPUT_FORMAT_JSON)
        if faulty:
            assert checks['numbers'] is False and checks['arguments'] is False, record['metrics']
            assert record['metrics']['invented_numbers'] == ['15']
        else:
            assert all(checks.values()), (record['variant'], record['metrics'])


def test_the_rescore_rebuilds_the_report_without_any_call(dry_run):
    out_dir, _records = dry_run
    tool.main(['--rescore', str(out_dir)])
    assert (out_dir / 'report_rescored.md').read_text(encoding='utf-8') \
        == (out_dir / 'report.md').read_text(encoding='utf-8')


def test_claude_joins_the_matrix_only_with_its_key(monkeypatch):
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    with pytest.raises(SystemExit, match='ANTHROPIC_API_KEY'):
        tool.check_models(['openai_deal_health', 'claude_deal_health'], dry_run=False)
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'sk-ant-test-not-a-real-key')
    tool.check_models(['openai_deal_health', 'claude_deal_health'], dry_run=False)
