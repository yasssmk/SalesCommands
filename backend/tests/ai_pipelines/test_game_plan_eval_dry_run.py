# backend/tests/ai_pipelines/test_game_plan_eval_dry_run.py
"""
Sprint 2 Game Plan, G13 — the Game Plan evaluation end to end, OFFLINE:
evals/game_plan/run_game_plan_eval.py --dry-run seeds the 6 fictitious cases
(the standard creation paths), runs the REAL assembler and PrepCallPipeline
on every cell (models X / Y) with a fixed-answer provider (no network),
scores each recorded call and writes the report. Everything it created is
rolled back.
"""

import pytest

from evals.game_plan import run_game_plan_eval as tool
from evals.game_plan import scoring


pytestmark = pytest.mark.django_db


@pytest.fixture
def dry_run(tmp_path):
    from app_modules.ai_pipelines.models import AIPipelineRun, PrepCallSnapshot
    from end_users.models import ClientAccount
    before = (ClientAccount.objects.count(), AIPipelineRun.objects.count(), PrepCallSnapshot.objects.count())
    out_dir = tool.main(['--dry-run', '--out', str(tmp_path / 'run')])
    after = (ClientAccount.objects.count(), AIPipelineRun.objects.count(), PrepCallSnapshot.objects.count())
    records = list(tool.load_records(out_dir, sorted(p.name for p in out_dir.iterdir() if p.is_dir())))
    return out_dir, records, before, after


def test_the_dry_run_plays_the_matrix_writes_the_report_and_leaves_nothing(dry_run):
    out_dir, records, before, after = dry_run

    assert len(tool.CASES) == 6
    assert len(records) == 12                                  # 6 cases x 2 models x n=1
    assert {r['provider_key'] for r in records} == {'openai_prep_call', 'openai_prep_call_challenger'}
    assert after == before                                     # nothing left in the database
    report = (out_dir / 'report.md').read_text(encoding='utf-8')
    for case in tool.CASES:
        assert f'## Cas `{case}`' in report
    assert '## Récapitulatif' in report and 'PARSE_ERROR' in report and '> 12 s' in report
    assert 'closing sobre' in report and 'lisibilité : part > 15 mots / mots moy.' in report   # G13f
    assert 'jargon théorique visible (appels)' in report and '(jargon) — section `messages[0].body`' in report
    # G13c: a finding is shown with its section and its excerpt.
    assert '- `37` (chiffre) — section `context` — « Reducing IT maintenance by 37 %' in report
    # G13d: the findings of EVERY call, and the slot findings with their excerpt.
    assert report.count('**Constats des 1 appel(s)** :') == 12
    assert "(créneau) — section `messages[0].body` — « Hello Ivan, I've sent you an invitation" in report
    assert (out_dir / 'summary.csv').exists() and (out_dir / 'summary.md').exists()


def test_the_prompts_carry_the_participants_by_first_name_only(dry_run):
    _out, records, _b, _a = dry_run
    for record in records:
        prompt = record['attempts'][0]['user']
        assert record['metrics']['last_names_in_prompt'] == [], record['variant']
        expected = tool._expected(record['case'])
        # The people DO reach the prompt — by their label (non-vacuity of the
        # « no last name » check, and of the homonym labels P1 / P2).
        for ref in expected.get('participants') or expected.get('languages'):
            assert ref in prompt, (record['variant'], ref)


def test_each_case_takes_its_output_kind_and_schema(dry_run):
    _out, records, _b, _a = dry_run
    for record in records:
        expected = tool._expected(record['case'])
        assert record['output_kind'] == expected['output_kind']
        sent = record['attempts'][0]['response_schema']
        assert sent == ('prep_call_messages_v2' if expected['output_kind'] == 'MESSAGE'
                        else 'prep_call_game_plan_v2_1')


def test_the_checks_run_on_every_call_and_catch_the_planted_faults(dry_run):
    _out, records, _b, _a = dry_run
    for record in records:
        metrics, checks = record['metrics'], scoring.checks(record['metrics'])
        cell = (record['case'], record['provider_key'])
        if cell == ('call_mid_cycle', 'openai_prep_call_challenger'):
            # G13f — the closing is not sober (and its slot is an invented one).
            assert checks['closing'] is False and checks['slots'] is False
            assert metrics['closing_findings'] == {
                'durations': ['45-minute security review'], 'slots': ['10:00', '3 December'],
                'agreement': False}
        elif cell == ('email_fr_profile', 'openai_prep_call_challenger'):
            # G13g — jargon is a measure: every check passes, the jargon is listed.
            assert all(v is not False for v in checks.values()), (record['variant'], metrics)
            assert [f['value'] for f in metrics['theory_jargon']] == ['pathos']
        elif cell == ('trap_no_figures', 'openai_prep_call_challenger'):
            assert checks['numbers'] is False and metrics['invented_numbers'] == ['37', '430']
        elif cell == ('linkedin_default', 'openai_prep_call_challenger'):
            assert checks['slots'] is False
            assert [f['value'] for f in metrics['invented_slots']] == ['heure: 10:00', "action: I've sent"]
        elif cell == ('demo_end_of_cycle', 'openai_prep_call'):
            assert metrics['answered'] is False
            assert metrics['parse_error_cause'] == 'last_name_false_reject'
        else:
            assert all(v is not False for v in checks.values()), (record['variant'], metrics)
            assert record['error'] is None, record['error']


def test_a_rescore_of_a_run_made_with_the_former_entries_stays_right(dry_run, tmp_path):
    """G13b: the first real run was recorded under openai_prep_call_terra /
    openai_prep_call (then gpt-4o-mini). The report labels each cell with the
    model RECORDED in its calls — not today's config, which has no
    openai_prep_call_terra and maps openai_prep_call to gpt-5.6-terra."""
    import json
    out_dir, _records, _b, _a = dry_run
    former = tmp_path / 'former'
    renamed = {'openai_prep_call': ('openai_prep_call_terra', 'gpt-5.6-terra'),
               'openai_prep_call_challenger': ('openai_prep_call', 'gpt-4o-mini')}
    for path in out_dir.glob('*/call_*.json'):
        record = json.loads(path.read_text(encoding='utf-8'))
        key, model = renamed[record['provider_key']]
        record.update(provider_key=key, model=model,
                      variant=tool.variant_name(record['case'], key))
        target = former / record['variant'] / path.name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(record), encoding='utf-8')

    tool.main(['--rescore', str(former)])

    report = (former / 'report_rescored.md').read_text(encoding='utf-8')
    assert '| gpt-5.6-terra (`openai_prep_call_terra`) |' in report
    assert '| gpt-4o-mini (`openai_prep_call`) |' in report


def test_the_report_lists_the_findings_of_every_call_not_only_the_first():
    """G13d: with --n 3, a finding of call 2 or 3 is listed too."""
    def record(call, value):
        return {'call': call, 'metrics': {
            'invented_numbers': [value] if value else [],
            'findings_context': [{'kind': 'number', 'value': value, 'path': 'context',
                                  'excerpt': f'… {value} % …'}] if value else []}}

    lines = tool._all_calls_findings([record(1, None), record(2, '15'), record(3, '40')])

    text = '\n'.join(lines)
    assert '**Constats des 3 appel(s)** :' in text
    assert '- appel 1 : aucun' in text
    assert '- `15` (chiffre) — section `context` — « … 15 % … »' in text
    assert '- `40` (chiffre)' in text and '- appel 3 :' in text
