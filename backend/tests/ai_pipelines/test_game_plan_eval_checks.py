# backend/tests/ai_pipelines/test_game_plan_eval_checks.py
"""
Sprint 2 Game Plan, G13 — the checks of the Game Plan evaluation
(evals/game_plan/scoring.py), proved on outputs written by hand: a correct
one passes, a faulty one is caught. Pure functions, no database.
"""

import copy

import pytest

from evals.game_plan import scoring


_PLAN = {
    'context': 'Nadia carries the need.',
    'objective': {'plans': [{'label': 'A', 'goal': 'g', 'success_criteria': 's'},
                            {'label': 'B', 'goal': 'g', 'success_criteria': 's'}]},
    'client_expectations': ['A clear plan.'],
    'opening': {'objective': 'o', 'time': 't', 'client_agenda': 'c', 'our_agenda': 'u',
                'expected_outcome': 'e'},
    'discovery': {'missing_info': [{'item': 'The IT security review', 'question': 'Who runs it?'}],
                  'conviction': {axis: {'reading': 'r', 'question': 'q'}
                                 for axis in ('needs_and_urgency', 'credibility', 'fit_and_value')}},
    'argumentation': [],
    'closing': {'next_step': 'n', 'with_whom': 'Nadia', 'when': 'w', 'keep_control': 'k'},
    'product_pitch': [],
    'participants': [{'ref': 'Nadia', 'angle': 'Her words.'}, {'ref': 'P1 Marc (IT)', 'angle': 'Security.'}],
    'campaign_diagnostic': None,
}
_EXPECTED_PLAN = {'output_kind': 'PLAN', 'participants': ['Nadia', 'P1 Marc (IT)'],
                  'dh_missing_any_of': ['security'], 'campaign_diagnostic': False,
                  'planted_last_names': ['Okafor', 'Lefort']}


def _plan(**overrides):
    plan = copy.deepcopy(_PLAN)
    plan.update(overrides)
    return plan


def _score(parsed, expected=_EXPECTED_PLAN, prompt='Nadia Marc IT', **kwargs):
    return scoring.score_call(parsed=parsed, prompt=prompt, user_prompt=prompt,
                              expected=expected, **kwargs)


def test_a_correct_plan_passes_every_check():
    checks = scoring.checks(_score(_PLAN))
    assert checks['language'] is None and checks['subject'] is None      # not a message
    assert all(v for k, v in checks.items() if k not in ('language', 'subject')), checks


# =============================================================================
# THE NEW PLAN CHECKS — each catches its fault
# =============================================================================

def test_a_participant_without_angle_is_caught():
    parsed = _plan(participants=[{'ref': 'Nadia', 'angle': 'Her words.'}, {'ref': 'P1 Marc (IT)', 'angle': ' '}])
    assert scoring.participants_covered(parsed, _EXPECTED_PLAN['participants']) == ['P1 Marc (IT)']
    assert scoring.checks(_score(parsed))['participants'] is False


@pytest.mark.parametrize('labels', [[], ['B'], ['A', 'C'], ['A', 'B', 'C', 'A']])
def test_plans_must_be_a_b_c_in_order_three_at_most(labels):
    parsed = _plan(objective={'plans': [{'label': x, 'goal': 'g', 'success_criteria': 's'} for x in labels]})
    assert scoring.plans_ok(parsed) is False


def test_three_plans_are_fine():
    parsed = _plan(objective={'plans': [{'label': x, 'goal': 'g', 'success_criteria': 's'} for x in 'ABC']})
    assert scoring.plans_ok(parsed) is True


def test_a_missing_opening_part_is_caught():
    parsed = _plan(opening={**_PLAN['opening'], 'client_agenda': ''})
    assert scoring.opening_missing(parsed) == ['client_agenda']
    assert scoring.checks(_score(parsed))['opening'] is False


def test_the_discovery_must_reuse_the_deal_health_missing_info():
    parsed = _plan(discovery={**_PLAN['discovery'],
                              'missing_info': [{'item': 'The budget', 'question': 'Who pays?'}]})
    assert scoring.discovery_covers_dh(parsed, ['security']) is False
    assert scoring.discovery_covers_dh(_PLAN, ['security']) is True
    assert scoring.discovery_covers_dh(_PLAN, None) is None              # no DH missing info


def test_campaign_diagnostic_only_for_the_campaign_case():
    with_diag = _plan(campaign_diagnostic={'reading': 'Two calls unanswered.', 'next_move': 'Email.'})
    assert scoring.campaign_diagnostic_ok(with_diag, True) is True
    assert scoring.campaign_diagnostic_ok(_PLAN, True) is False          # expected, absent
    assert scoring.campaign_diagnostic_ok(with_diag, False) is False     # present out of case
    assert scoring.campaign_diagnostic_ok(_PLAN, False) is True


# =============================================================================
# THE MESSAGE CHECKS
# =============================================================================

_EXPECTED_EMAIL = {'output_kind': 'MESSAGE', 'channel': 'EMAIL', 'languages': {'Claire': 'fr'},
                   'planted_last_names': ['Morel']}


def _messages(language='fr', subject='Notre prochaine étape'):
    return {'messages': [{'ref': 'Claire', 'language': language, 'subject': subject,
                          'body': 'Bonjour Claire, pouvons-nous caler un échange ?'}]}


def test_a_correct_email_passes():
    checks = scoring.checks(_score(_messages(), _EXPECTED_EMAIL, prompt='Claire'))
    assert checks['language'] and checks['subject'] and checks['schema'], checks
    assert checks['plans'] is None                                       # not a plan


def test_a_message_in_the_wrong_language_is_caught():
    assert scoring.wrong_languages(_messages('en'), {'Claire': 'fr'}) == {'Claire': ('fr', 'en')}
    assert scoring.wrong_languages({'messages': []}, {'Claire': 'fr'}) == {'Claire': ('fr', None)}


def test_the_subject_rule_per_channel():
    assert scoring.subject_ok(_messages(subject=''), 'EMAIL') is False
    assert scoring.subject_ok(_messages(subject=None), 'LINKEDIN') is True
    assert scoring.subject_ok(_messages(subject='Hello'), 'LINKEDIN') is False
    assert scoring.subject_ok({'messages': []}, 'EMAIL') is False


# =============================================================================
# THE GENERIC CHECKS, REUSED — on the Game Plan's output
# =============================================================================

def test_an_invented_figure_is_caught_the_red_ruban_case():
    parsed = _plan(context='Reducing IT maintenance by 20 % saves 8 hours per week.')
    assert scoring.checks(_score(parsed))['numbers'] is False
    assert _score(parsed)['invented_numbers'] == ['20', '8']
    # A figure of the pack is not invented (« 20 8 » would read as one
    # number: the space is a thousands separator for the reused detector).
    assert _score(parsed, prompt='Nadia Marc IT, 20 percent, 8 hours')['invented_numbers'] == []


def test_the_system_prompt_figures_are_not_evidence():
    """« 70% » / « 30% » are in the system prompt, never in the pack: a
    figure copied from it is still invented."""
    parsed = _plan(context='Spend 70% on selling.')
    metrics = scoring.score_call(parsed=parsed, prompt='SYSTEM 70% 30%\nNadia', user_prompt='Nadia',
                                 expected=_EXPECTED_PLAN)
    assert metrics['invented_numbers'] == ['70']


def test_the_plan_letters_and_refs_are_not_invented_names():
    parsed = _plan(context='Plan B is the fallback.')
    assert _score(parsed)['invented_names'] == []
    assert _score(_plan(context='Like Contoso did.'))['invented_names'] == ['Contoso']


def test_a_last_name_and_a_rhetoric_label_are_caught():
    assert scoring.checks(_score(_plan(context='Nadia Okafor decides.')))['first_names'] is False
    assert scoring.checks(_score(_plan(context='Use pathos here.')))['rhetoric'] is False


def test_the_nullable_campaign_diagnostic_is_schema_valid():
    assert scoring.schema_errors(_PLAN, scoring.schema_for('PLAN')) == []
    with_diag = _plan(campaign_diagnostic={'reading': 'r', 'next_move': 'n'})
    assert scoring.schema_errors(with_diag, scoring.schema_for('PLAN')) == []
    assert scoring.schema_errors(_plan(campaign_diagnostic='yes'), scoring.schema_for('PLAN')) != []
    assert scoring.schema_errors(_plan(campaign_diagnostic={'reading': 'r'}), scoring.schema_for('PLAN')) != []


# =============================================================================
# PARSE_ERROR — the cause, false rejections told apart
# =============================================================================

@pytest.mark.parametrize('error, raw, cause', [
    ('PromptParseError: run PARSE_ERROR: parse_error: The Game Plan names a classical rhetoric label.',
     '{"context": "pathos"}', 'rhetoric'),
    ('PromptParseError: run PARSE_ERROR: parse_error: The Game Plan writes 1 last name(s).',
     '{"closing": "Meet Sarah Price."}', 'last_name'),
    ('PromptParseError: run PARSE_ERROR: parse_error: The Game Plan writes 1 last name(s).',
     '{"client_expectations": ["See the price on their data."]}', 'last_name_false_reject'),
    ('PromptParseError: run PARSE_ERROR: parse_error: Invalid "objective.plans": 1 to 3 plans.',
     '{}', 'structure'),
    (None, None, ''),
    ('LLMTimeoutError: run TIMEOUT: timeout', None, ''),
])
def test_the_parse_error_cause(error, raw, cause):
    assert scoring.parse_error_cause(error, raw, ['Price', 'Becker']) == cause


# =============================================================================
# G13b — the false positives of the first real run, and what stays invented
# =============================================================================

_PACK = 'Corvane Foods. The demo is planned on 2026-12-02. Ivan books the dock slots by phone.'


@pytest.mark.parametrize('text', [
    # Meeting durations the plan proposes.
    'Propose a 30-minute working session.',
    'Run a 45-minute targeted demonstration.',
    'Book a 20-minute discovery meeting.',
    'Ask for 30 minutes.',
    'A one-hour call with Tom.',
    # Dates (were read as 22026 / 32026) and times.
    'Meet on December 2, 2026 or December 3, 2026.',
    'On 2 December 2026 at 10:00.',
    'Confirm 2026-12-02.',
    'Le 2 décembre 2026 à 14h30.',
    'By Friday 10am or 2:30 pm.',
])
def test_a_meeting_duration_a_date_or_a_time_is_not_invented(text):
    assert scoring.invented_numbers({'context': text}, _PACK) == [], text


@pytest.mark.parametrize('text, found', [
    ('Reducing IT maintenance by 20 % saves 8 hours per week.', ['20', '8']),   # RED RUBAN
    ('Lead with a 20 % gain.', ['20']),
    ('It frees over one month of labor a year.', ['over one month']),
    ('We lose 8 hours per week.', ['8']),
    ('Take 30 minutes per week to review.', ['30']),
    ('A budget of 50 000 euros.', ['50000']),
    ('In 2026 the team saves 2000 hours.', ['2000']),       # a year is a date, a volume is not
])
def test_a_percentage_an_amount_a_gain_or_a_volume_stays_invented(text, found):
    assert scoring.invented_numbers({'context': text}, _PACK) == found, text


@pytest.mark.parametrize('text', [
    'Show the plan on Corvane-data.',                       # a compound of a known name
    'Would Tuesday or Wednesday work, Ivan?',
    'Saturday or Sunday works.',
    'Shall we meet Tue or Wed?',
])
def test_a_known_name_compound_or_a_weekday_is_not_invented(text):
    assert scoring.invented_names({'context': text}, _PACK) == [], text


def test_a_compound_of_a_common_word_stays_a_finding():
    assert scoring.invented_names({'context': 'Like Contoso-data deals.'},
                                  'The data is booked.') == ['Contoso-data']
