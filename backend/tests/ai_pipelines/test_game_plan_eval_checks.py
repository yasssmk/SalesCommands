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
    'closing': {'next_step': 'n', 'with_whom': 'Nadia', 'when': 'w',
                'keep_control': 'Get agreement on it before hanging up.'},   # G13f: an agreement asked
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


# =============================================================================
# G13c — the uncovered duration forms, and the excerpt of every finding
# =============================================================================

@pytest.mark.parametrize('text', [
    'Book a 20‑minute discovery meeting.',         # non-breaking hyphen U+2011
    'A 45–minute demo on their data.',              # en dash
    'Propose a 30 minute call.',                    # non-breaking space
    'Je vous propose un échange de 30 minutes.',
    'Un point rapide de 20 min jeudi ?',
    '30 minutes d’échange suffiront.',
    'Pouvez-vous m’accorder 10 minutes ?',
])
def test_a_typographic_or_french_meeting_duration_is_not_invented(text):
    assert scoring.invented_numbers({'messages': [{'body': text}]}, _PACK) == [], text


@pytest.mark.parametrize('text, found', [
    ('Un appel de 30 minutes par semaine.', ['30']),     # a rate, not a meeting
    ('Gagnez 10 heures par semaine.', ['10']),
    ('Reducing IT maintenance by 20 % saves 8 hours per week.', ['20', '8']),   # RED RUBAN
])
def test_a_french_or_typographic_rate_stays_invented(text, found):
    assert scoring.invented_numbers({'messages': [{'body': text}]}, _PACK) == found, text


def test_each_finding_carries_its_section_and_an_excerpt():
    parsed = _plan(
        closing={**_PLAN['closing'], 'next_step': 'Book a 30-minute call. Lead with the 20 % gain '
                                                  'they will see in the first weeks of the pilot.'},
        context='It frees over one month of labor. Like Contoso did.',
    )
    metrics = _score(parsed)
    context = {(f['kind'], f['value']): f for f in metrics['findings_context']}

    assert context[('number', '20')]['path'] == 'closing.next_step'
    assert '20 % gain' in context[('number', '20')]['excerpt']
    assert ('number', '30') not in context                       # the meeting duration is allowed
    assert context[('number', 'over one month')]['path'] == 'context'
    assert context[('name', 'Contoso')]['excerpt'].endswith('Like Contoso did.')
    assert len(context[('number', '20')]['excerpt']) <= 2 * scoring.EXCERPT_RADIUS + 10


def test_a_message_finding_names_its_message():
    parsed = {'messages': [{'ref': 'Claire', 'language': 'fr', 'subject': 's',
                            'body': 'Bonjour Claire, nos clients gagnent 15 % de temps.'}]}
    [finding] = scoring.locate_findings(parsed, ['15'], [])
    assert finding['path'] == 'messages[0].body' and '15 %' in finding['excerpt']


# =============================================================================
# G13d — a duration on its own is logistics; no invented slot, no claimed action
# =============================================================================

_SLOT_PACK = ('Corvane Foods. The board reviews the budget on 2026-12-09. '
              'The meeting is planned on 2026-11-28.')


@pytest.mark.parametrize('text', [
    '15 minutes suffiront.',
    'Spend 20 minutes on the review.',
    '45 minutes, then questions.',
    'Rendez-vous à 10 h.',                        # a time (the slot check judges it)
])
def test_a_duration_on_its_own_is_logistics(text):
    assert scoring.invented_numbers({'context': text}, _SLOT_PACK) == [], text


@pytest.mark.parametrize('text, found', [
    ('Take 30 minutes per week.', ['30']),        # a rate
    ('It saves 8 hours.', ['8']),                 # a gain before
    ('Over 8 hours of labor saved.', ['8']),      # a gain after
    ('Gagnez 10 heures par semaine.', ['10']),
])
def test_a_duration_with_a_rate_or_a_gain_stays_invented(text, found):
    assert scoring.invented_numbers({'context': text}, _SLOT_PACK) == found, text


@pytest.mark.parametrize('text, values', [
    ('Je vous envoie une invitation de 30 minutes pour mardi 1er décembre à 10 h.',
     ['date: 1er décembre', 'heure: à 10 h', 'action: Je vous envoie une invitation']),   # the real case
    ("I've sent you an invitation for Tuesday at 10:00.", ['heure: 10:00', "action: I've sent"]),
    ('I booked a slot.', ['action: I booked']),
    ("I'm sending you a calendar invite.", ["action: I'm sending you a calendar"]),
    ("L'invitation est envoyée.", ['action: invitation est envoyée']),
    ("J'ai réservé un créneau.", ["action: J'ai réservé"]),
    ('Shall we meet at 3pm?', ['heure: 3pm']),
    ('Shall we meet on 3 December?', ['date: 3 December']),
    ('How about 12/03?', ['date: 12/03']),
])
def test_an_invented_slot_or_a_claimed_action_is_caught(text, values):
    assert [f['value'] for f in scoring.invented_slots({'messages': [{'body': text}]}, _SLOT_PACK)] == values


@pytest.mark.parametrize('text', [
    'Mardi ou mercredi ?',
    'Would Tuesday or Wednesday work?',
    'En début de semaine prochaine ?',
    'Early next week: [date and time]?',
    'Je vous propose [date et heure].',
    'Before the board on 9 December.',            # a date of the pack
    'Send the invitation today.',                 # an instruction to the rep
    "I'll send an invitation once you confirm.",  # an intention, not a claim
    'Je vous envoie ce message pour faire le point.',
    'A 30-minute call next week.',
])
def test_an_open_window_a_placeholder_or_a_pack_date_is_fine(text):
    assert scoring.invented_slots({'messages': [{'body': text}]}, _SLOT_PACK) == [], text


def test_the_slot_check_is_in_the_recap_and_carries_its_excerpt():
    parsed = _messages(subject='Prochaine étape')
    parsed['messages'][0]['body'] = 'Je vous envoie une invitation pour mardi 1er décembre à 10 h.'
    metrics = _score(parsed, _EXPECTED_EMAIL, prompt='Claire')
    assert scoring.checks(metrics)['slots'] is False
    slot = next(f for f in metrics['findings_context'] if f['kind'] == 'slot')
    assert slot['path'] == 'messages[0].body' and 'mardi 1er décembre' in slot['excerpt']
    assert scoring.checks(_score(_PLAN))['slots'] is True


# =============================================================================
# G13e — an English contraction is not a name
# =============================================================================

@pytest.mark.parametrize('text', [
    'Then I’d suggest a review.',
    'Then I’ll call you.',
    "Great, I'll send it.",                       # straight apostrophe
    'Thanks — We’re ready.',
    'So I’m sure.',
    'Good, They’ve agreed.',
    'Yes, Don’t push.',
    'Fine, Can’t wait.',
    'Sure, Won’t hurt.',
])
def test_an_english_contraction_is_not_an_invented_name(text):
    assert scoring.invented_names({'context': text}, 'Claire Corvane.') == [], text


def test_a_name_with_an_apostrophe_stays_a_finding():
    assert scoring.invented_names({'context': 'Ask O’Neil first.'}, 'Claire Corvane.') == ['O’Neil']


# =============================================================================
# G13f — the closing, sober; readable in the middle of a meeting
# =============================================================================

_SOBER = {'next_step': 'Run the security review that validates technical fit.', 'with_whom': 'Marc',
          'when': 'After the pilot recap.',
          'keep_control': 'Get agreement on the security review and book it before hanging up.'}


def test_a_sober_closing_passes():
    parsed = _plan(closing=_SOBER)
    assert scoring.closing_findings(parsed) == {'durations': [], 'slots': [], 'agreement': True}
    assert scoring.checks(_score(parsed))['closing'] is True


@pytest.mark.parametrize('field, text, key', [
    ('next_step', 'A 45-minute security review.', 'durations'),
    ('when', 'Spend 20 minutes on it.', 'durations'),
    ('when', 'On 3 December.', 'slots'),
    ('when', 'Tuesday at 10:00.', 'slots'),
    ('when', 'Le 3 décembre à 10 h.', 'slots'),
])
def test_a_duration_a_date_or_a_time_in_the_closing_is_caught(field, text, key):
    parsed = _plan(closing={**_SOBER, field: text})
    assert scoring.closing_findings(parsed)[key], text
    assert scoring.checks(_score(parsed))['closing'] is False


def test_a_closing_without_an_agreement_asked_is_caught():
    parsed = _plan(closing={**_SOBER, 'keep_control': 'Send the deck today.',
                            'next_step': 'Run the security review.'})
    assert scoring.closing_findings(parsed)['agreement'] is False
    assert scoring.checks(_score(parsed))['closing'] is False


@pytest.mark.parametrize('text', [
    "Obtenir l'accord de Marc et caler la revue avant de raccrocher.",
    'Confirm the review with Marc before the end.',
    'Get his commitment to the pilot.',
])
def test_an_agreement_is_recognised(text):
    assert scoring.closing_findings(_plan(closing={**_SOBER, 'keep_control': text}))['agreement'], text


def test_readability_measures_the_lines_over_the_maximum():
    from app_modules.ai_pipelines.constants import PREP_CALL_LINE_MAX_WORDS
    long_line = ' '.join(['word'] * (PREP_CALL_LINE_MAX_WORDS + 1))
    parsed = _plan(context=' '.join(['long'] * 60),                      # the context is not an item
                   client_expectations=[long_line, 'Show the pilot plan.'])
    found = scoring.readability(parsed)
    assert found['over'] == [('client_expectations[0]', PREP_CALL_LINE_MAX_WORDS + 1)]
    assert found['over_share'] == round(1 / found['items'], 3)
    assert found['mean_words'] > 0
    assert scoring.readability(_PLAN)['over'] == []
