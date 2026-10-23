# backend/tests/evals/test_next_steps_scoring.py
"""
Sprint Next steps 3.0 — scoring of the next_steps eval
(evals/next_steps/scoring.py + expected.json): tolerant match, invention,
date window, ground-truth validity, required_from, fusion, leak guard. Pure
functions, no database.
"""

import copy
from pathlib import Path

import pytest

from app_modules.ai_pipelines.prompts.next_steps.next_steps_v1 import (
    build_next_steps_request,
)
from app_modules.ai_pipelines.prompts.transcript_signals.system import SYSTEM_PROMPT
from app_modules.ai_pipelines.services.transcript_text import TranscriptText
from evals.next_steps import scoring


EVAL_DIR = Path(scoring.__file__).resolve().parent
EXPECTED = scoring.load_expected(EVAL_DIR / 'expected.json')
ITEMS = {item['id']: item for item in EXPECTED['items']}


def _transcript(key):
    return (EVAL_DIR / EXPECTED['transcripts'][key]['file']).resolve().read_text(encoding='utf-8')


def _matching(title, transcript):
    """The ids of the items of `transcript` a next step titled `title` matches."""
    return [i['id'] for i in EXPECTED['items']
            if i['transcript'] == transcript and scoring.matches({'suggested_title': title}, i)]


# =============================================================================
# GROUND TRUTH
# =============================================================================

class TestExpected:

    def test_the_po_ground_truth(self):
        required = {i['id'] for i in EXPECTED['items'] if scoring.is_required(i, 'v1')}
        assert required == {'A', 'B', 'C_prospect', 'C_vendeur', 'D'}
        # C_suivi and K: informative in v1, required from prompt v2 on.
        assert (ITEMS['C_suivi']['required_from'], ITEMS['K']['required_from']) == ('v2', 'v2')
        assert {i['id'] for i in EXPECTED['items'] if scoring.is_required(i, 'v2')} == \
            required | {'C_suivi', 'K'}
        # K (PO, after the v2 run): the prospect validates the business case
        # before the 2027 budget closes.
        assert (ITEMS['K']['expected_types'], ITEMS['K']['carried_by_prospect'],
                ITEMS['K']['date_window'], ITEMS['K']['expected_step']) == (
            ['TASK'], True, ['2026-12-14', '2026-12-15'], 'BUSINESS_CASE')
        # C_prospect: the presentation, no date said; C_suivi follows the
        # prospect's deadline, budget included.
        assert ITEMS['C_prospect']['date_window'] is None
        assert ITEMS['C_suivi']['date_window'] == ['2026-11-15', '2026-12-16']
        # Logistix informative items (never in the recall).
        assert {i: (ITEMS[i]['expected_types'], ITEMS[i]['required_from'])
                for i in ('E', 'F', 'G', 'H')} == {
            'E': (['EMAIL'], None), 'F': (['TASK'], None),
            'G': (['MEETING'], None), 'H': (['EMAIL'], None)}
        # Atelier informative items (PO, after the Terra v1 run).
        assert (ITEMS['I']['expected_types'], ITEMS['I']['required_from'],
                ITEMS['I']['date_window'][1]) == (['EMAIL'], None, '2026-11-15')
        assert (ITEMS['J']['expected_types'], ITEMS['J']['required_from'],
                ITEMS['J']['date_window']) == (['TASK'], None, None)
        assert ITEMS['A']['expected_types'] == ['EMAIL']
        assert ITEMS['A']['date_window'][1] == '2026-10-23'          # avant vendredi
        assert scoring.in_window('2026-11-03', ITEMS['B']['date_window'])
        assert ITEMS['B']['expected_types'] == ['MEETING']
        assert ITEMS['C_prospect']['carried_by_prospect'] is True
        assert ITEMS['D']['date_window'][1] == '2026-11-30'
        assert ITEMS['D']['expected_types'] == ['MEETING']

    def test_transcripts_exist_and_their_header_gives_the_date(self):
        from app_modules.ai_pipelines.services.transcript_text import header_date
        for key, case in EXPECTED['transcripts'].items():
            assert header_date(_transcript(key)) == case['conversation_date']

    @pytest.mark.parametrize('breakage, message', [
        (lambda d: d['items'][0].pop('date_window'), 'missing'),
        (lambda d: d['items'][0].update(transcript='nope'), 'unknown transcript'),
        (lambda d: d['items'][0].update(date_window=['2026-11-02', '2026-11-01']), 'empty date window'),
        (lambda d: d['items'][1].update(id=d['items'][0]['id']), 'duplicate id'),
        (lambda d: d['items'][0]['match'].update(all_of=[[]]), 'all_of'),
        (lambda d: d['items'][0].update(required_from='two'), 'required_from'),
        (lambda d: d['items'][0]['quote_match'].pop('any_of'), 'quote_match'),
    ])
    def test_a_malformed_ground_truth_is_refused(self, breakage, message):
        data = copy.deepcopy(EXPECTED)
        breakage(data)
        with pytest.raises(ValueError, match=message):
            scoring.validate_expected(data)


# =============================================================================
# TOLERANT MATCH
# =============================================================================

class TestTolerantMatch:

    def test_case_accents_and_punctuation_are_ignored(self):
        assert scoring.normalize("Rapport SOC-2 : sécurité d'hébergement") == \
            'rapport soc 2 securite d hebergement'

    def test_whole_word_unless_star(self):
        assert scoring.keyword_in('marc', scoring.normalize('Présenter à Marc'))
        assert not scoring.keyword_in('marc', scoring.normalize('Étude de marché'))
        assert scoring.keyword_in('rencontr*', scoring.normalize('Rencontrer le DSI'))
        assert not scoring.keyword_in('rencontr', scoring.normalize('Rencontrer le DSI'))

    @pytest.mark.parametrize('title, expected', [
        ('Envoyer le DPA et le rapport SOC 2', ['A']),
        ('Send the SOC2 report and DPA to Thomas', ['A']),
        ('Planifier la réunion sécurité avec Laurent Petit (DSI)', ['B']),
        ('Organiser un rendez-vous avec le DSI', ['B']),
        # A next step about the documents is A, never B.
        ('Envoyer les documents de sécurité avant la réunion avec Laurent', ['A']),
        ('Isabelle présente le business case au contrôleur de gestion puis à Marc', ['C_prospect']),
        ('Envoyer une première version du business case', ['C_vendeur']),
        ('Préparer le business case (ROI)', ['C_vendeur']),
        # The final version is not the v1 of next week: it is I.
        ('Finaliser le business case', ['I']),
        ('Envoyer la version finale du business case à Isabelle', ['I']),
        ('Send final business case before Nov 15', ['I']),
        # Isabelle presenting the final version is C_prospect, not I.
        ('Isabelle présente le business case final au contrôleur de gestion', ['C_prospect']),
        ('Lancer le pilote avec Karim', ['J']),
        ('Former Karim et son équipe', ['J2']),
        ('Relancer Isabelle sur la validation du business case', ['C_suivi']),
        ('Merci', []),
    ])
    def test_atelier_titles(self, title, expected):
        assert _matching(title, 'atelier') == expected

    @pytest.mark.parametrize('title, expected', [
        ('Rendez-vous avec Isabelle Roux (DAF)', ['D']),
        ('Présenter le business case à la DAF', ['D']),
        ('Meeting with the CFO', ['D']),
        # Preparing the business case is not the meeting.
        ('Préparer le business case pour Isabelle', ['F']),
        ('Envoyer la documentation technique à Thomas', ['E']),
        ('Prepare business case for Isabelle', ['F']),
        ('Organiser une session de sécurité avec le DSI', ['G']),
        ('Envoyer le questionnaire SOC 2', ['H']),
        ('Merci', []),
    ])
    def test_logistix_titles(self, title, expected):
        assert _matching(title, 'logistix') == expected

    def test_type_and_date_are_not_match_criteria(self):
        signal = {'suggested_title': 'Envoyer le DPA', 'suggested_activity_type': 'CALL',
                  'suggested_due_date': '2030-01-01'}
        assert scoring.matches(signal, ITEMS['A'])


# =============================================================================
# DATE WINDOW
# =============================================================================

class TestDateWindow:

    WINDOW = ['2026-10-20', '2026-10-23']

    @pytest.mark.parametrize('date, expected', [
        ('2026-10-20', True), ('2026-10-23', True),          # bounds included
        ('2026-10-22', True),
        ('2026-10-19', False), ('2026-10-24', False),
        (None, None), ('', None), ('vendredi', None),       # no (valid) date
    ])
    def test_in_window(self, date, expected):
        assert scoring.in_window(date, self.WINDOW) is expected

    def test_no_window_means_no_date_expected(self):
        assert scoring.in_window('2026-10-22', None) is None


class TestRequiredFrom:

    @pytest.mark.parametrize('required_from, version, expected', [
        ('v1', 'v1', True), ('v1', 'v2', True),
        ('v2', 'v1', False), ('v2', 'v2', True), ('v2', 'v10', True),
        (None, 'v2', False),          # informative
        ('v1', None, False),          # unknown prompt version
    ])
    def test_is_required(self, required_from, version, expected):
        assert scoring.is_required({'required_from': required_from}, version) is expected


# =============================================================================
# INVENTION
# =============================================================================

class TestInvention:

    TEXT = TranscriptText(_transcript('atelier'))

    @pytest.mark.parametrize('quote', [
        "Envoyez-les avant vendredi, s'il vous plaît.",
        'envoyez-les avant vendredi',                          # case, cut punctuation
        "Envoyez-les avant vendredi, s’il vous plaît.",        # typographic apostrophe
        # A speaker label copied at the head of a mid-line sentence: removed
        # first, as the server does (strip_speaker_label).
        'Thomas Lefèvre: Laurent veut les lire avant de vous rencontrer.',
    ])
    def test_a_transcript_quote_is_not_an_invention(self, quote):
        assert not scoring.is_invented(quote, self.TEXT)

    @pytest.mark.parametrize('quote', [
        'Isabelle a confirmé le budget de soixante-dix mille euros.',
        'Envoyez-les avant lundi',                              # one word changed
        '', None,
    ])
    def test_a_quote_not_in_the_transcript_is_an_invention(self, quote):
        assert scoring.is_invented(quote, self.TEXT)


# =============================================================================
# ONE CALL
# =============================================================================

def _ns(title, type_='TASK', date=None, quote="Envoyez-les avant vendredi, s'il vous plaît.", **extra):
    return {'suggested_title': title, 'suggested_activity_type': type_,
            'suggested_due_date': date, 'source_quote': quote, **extra}


class TestScoreCall:

    def _score(self, persisted, raw=None, version='v1'):
        return scoring.score_call(
            persisted=persisted, parsed={'signals': raw if raw is not None else persisted},
            items=[i for i in EXPECTED['items'] if i['transcript'] == 'atelier'],
            transcript=_transcript('atelier'), prompt_version=version, leaks=[],
        )

    def test_presence_type_date_duplicates_inventions(self):
        m = self._score([
            _ns('Envoyer le DPA et le SOC 2', 'EMAIL', '2026-10-23'),
            _ns('Transmettre le DPA', 'EMAIL', None),
            _ns('Réunion sécurité avec Laurent Petit', 'CALL', '2026-11-20',
                quote='Laurent a validé le projet.'),
            _ns('Commander des croissants', 'TASK'),
        ])
        assert (m['A_present'], m['A_matches'], m['A_type_ok'], m['A_date_in_window']) == \
            (True, 2, True, True)
        assert (m['B_present'], m['B_type_ok'], m['B_date_in_window']) == (True, False, False)
        assert (m['C_prospect_present'], m['C_prospect_type_ok'],
                m['C_prospect_date_in_window']) == (False, None, None)
        assert m['duplicates'] == 1
        assert m['inventions'] == 1
        assert m['unmatched'] == 1
        assert (m['emitted'], m['persisted']) == (4, 4)

    def test_a_matched_next_step_without_date(self):
        m = self._score([_ns('Envoyer le DPA', 'EMAIL', None)])
        assert (m['A_date_in_window'], m['A_date_missing']) == (None, True)

    def test_inventions_are_also_counted_on_the_raw_answer(self):
        raw = [_ns('Envoyer le DPA', quote='Phrase inventée de toutes pièces.')]
        m = self._score([], raw=raw)          # dropped before storage
        assert (m['inventions'], m['inventions_raw'], m['A_present']) == (0, 1, False)

    def test_new_fields_are_na_on_the_baseline_prompt(self):
        persisted = [_ns('Isabelle présente au contrôleur de gestion', carried_by_prospect=True,
                         suggested_topics='ROI', suggested_people_names=['Isabelle Roux'])]
        baseline = self._score(persisted)
        assert baseline['C_prospect_carried_ok'] is None
        assert baseline['new_suggested_topics'] is None
        assert baseline['people_names_not_in_transcript'] is None

        later = self._score(persisted, version='v2')
        assert later['C_prospect_carried_ok'] is True
        assert later['new_suggested_topics'] == 1
        assert later['new_carried_by_prospect'] == 1
        assert later['people_names_not_in_transcript'] == 0

    def test_a_date_on_an_item_without_window_is_not_scored(self):
        m = scoring.score_call(
            persisted=[_ns('Envoyer la documentation technique à Thomas', 'EMAIL', '2026-10-20',
                           quote="On a un connecteur Salesforce natif et le SSO Azure est supporté.")],
            parsed=None, items=[ITEMS['E']], transcript=_transcript('logistix'), prompt_version='v1')
        assert (m['E_present'], m['E_type_ok'], m['E_date_in_window']) == (True, True, None)

    def test_a_failed_call_scores_every_item_absent(self):
        m = scoring.score_call(persisted=[], parsed=None, items=list(ITEMS.values()),
                               transcript=_transcript('atelier'), prompt_version='v1')
        assert not any(m[f'{i}_present'] for i in ITEMS)
        assert m['prompt_leaks'] is None


# =============================================================================
# LEAK GUARD (point 7)
# =============================================================================

class TestLeakGuard:

    NAMES = EXPECTED['leak_guard']['names']
    N = EXPECTED['leak_guard']['ngram_words']

    def _leaks(self, system, user):
        return scoring.prompt_leaks(system, user, [_transcript(k) for k in EXPECTED['transcripts']],
                                    self.NAMES, self.N)

    def test_the_transcript_block_itself_is_not_a_leak(self):
        user = build_next_steps_request(_transcript('atelier'))
        assert self._leaks(SYSTEM_PROMPT, user) == []

    def test_the_production_prompt_carries_no_example_from_the_eval_transcripts(self):
        user = build_next_steps_request('Bonjour.')
        assert self._leaks(SYSTEM_PROMPT, user) == []

    def test_a_transcript_passage_in_an_example_is_a_leak(self):
        user = 'EXAMPLE: "Envoyez-les avant vendredi, s\'il vous plaît."\n' + \
            build_next_steps_request('Bonjour.')
        assert 'envoyez les avant vendredi s' in self._leaks(SYSTEM_PROMPT, user)

    def test_a_transcript_name_in_an_example_is_a_leak(self):
        assert self._leaks('Example: Laurent Petit, CIO', 'x') == ['Laurent Petit']


# =============================================================================
# FUSION — a next step matched to an item, justified by ANOTHER absent item
# =============================================================================

class TestFusion:

    RDV_ISABELLE = 'Mais avant ça, on devra forcément faire un rendez-vous avec Isabelle Roux, notre DAF.'

    def _score(self, persisted):
        return scoring.score_call(
            persisted=persisted, parsed={'signals': persisted},
            items=[i for i in EXPECTED['items'] if i['transcript'] == 'logistix'],
            transcript=_transcript('logistix'), prompt_version='v1')

    def test_the_po_baseline_case_d_absorbed_by_f(self):
        """logistix/call_01 of the PO baseline: the meeting with Isabelle merged
        into "Prepare business case for Isabelle" (TASK), quoting the meeting."""
        m = self._score([_ns('Prepare business case for Isabelle', 'TASK', '2026-11-30',
                             quote=self.RDV_ISABELLE)])
        assert (m['D_present'], m['F_present']) == (False, True)
        assert m['D_absorbed_by'] == 'F'
        assert (m['fusions'], m['fusion_detail']) == (1, 'F<-D')
        assert m['unmatched'] == 0

    def test_a_shared_justification_is_not_a_fusion(self):
        """D is present: F quoting the same sentence absorbed nothing."""
        m = self._score([
            _ns('Rendez-vous avec Isabelle Roux (DAF)', 'MEETING', quote=self.RDV_ISABELLE),
            _ns('Prepare business case for Isabelle', 'TASK', quote=self.RDV_ISABELLE),
        ])
        assert (m['D_present'], m['F_present'], m['fusions'], m['D_absorbed_by']) == \
            (True, True, 0, '')

    def test_an_own_quote_is_not_a_fusion(self):
        m = self._score([_ns('Prepare business case for Isabelle', 'TASK',
                             quote='elle voudra voir un business case avec un retour sur '
                                   'investissement chiffré.')])
        assert (m['F_present'], m['fusions'], m['D_absorbed_by']) == (True, 0, '')

    def test_an_unmatched_next_step_never_fuses(self):
        m = self._score([_ns('Commander des croissants', quote=self.RDV_ISABELLE)])
        assert (m['fusions'], m['unmatched'], m['D_absorbed_by']) == (0, 1, '')


# =============================================================================
# RECAP — the recall follows the run's prompt version (required_from)
# =============================================================================

def test_the_recall_follows_the_prompt_version():
    from evals.next_steps.run_next_steps_eval import _recap

    persisted = [_ns('Relancer Isabelle sur la validation', 'CALL')]    # C_suivi only
    metrics = scoring.score_call(
        persisted=persisted, parsed=None,
        items=[i for i in EXPECTED['items'] if i['transcript'] == 'atelier'],
        transcript=_transcript('atelier'), prompt_version='v1')
    rows = [{'variant': 'atelier', 'call': 1, 'error': '', 'error_type': '',
             'duration_ms': 1, 'wall_ms': 1, **metrics}]

    def line(version, start, section='## Attendus'):
        lines = _recap(rows, version)
        return next(x for x in lines[lines.index(next(h for h in lines if h.startswith(section))):]
                    if x.startswith(start))

    def recall(version):
        return line(version, '| atelier | 1 |', section='## Bruit').split(' | ')[2]

    assert recall('v1') == '0/4'
    assert line('v1', '| atelier | C_suivi').startswith('| atelier | C_suivi (info) |')
    assert recall('v2') == '1/6'          # + C_suivi and K
    assert line('v2', '| atelier | C_suivi').startswith('| atelier | C_suivi |')


def test_the_v1_and_the_final_version_are_two_distinct_items():
    """A run emitting only the final version: I present, C_vendeur absent and
    not absorbed (I's quote is its own)."""
    m = scoring.score_call(
        persisted=[_ns('Envoyer la version finale du business case', 'EMAIL', '2026-11-14',
                       quote='Il me faut la version finale avant le quinze novembre')],
        parsed=None, items=[i for i in EXPECTED['items'] if i['transcript'] == 'atelier'],
        transcript=_transcript('atelier'), prompt_version='v1')
    assert (m['I_present'], m['I_type_ok'], m['I_date_in_window']) == (True, True, True)
    assert (m['C_vendeur_present'], m['C_vendeur_absorbed_by'], m['unmatched']) == (False, '', 0)


def test_a_false_flag_is_not_counted_as_a_filled_new_field():
    """v2 answers always carry carried_by_prospect: only true counts."""
    raw = [_ns('Envoyer le DPA', carried_by_prospect=False),
           _ns('Isabelle présente au contrôleur de gestion', carried_by_prospect=True)]
    m = scoring.score_call(
        persisted=raw, parsed={'signals': raw},
        items=[i for i in EXPECTED['items'] if i['transcript'] == 'atelier'],
        transcript=_transcript('atelier'), prompt_version='v2')
    assert m['new_carried_by_prospect'] == 1


# =============================================================================
# EXPECTED STEP (PO, before the v2 measure)
# =============================================================================

def test_the_po_expected_steps():
    assert {i: ITEMS[i]['expected_step'] for i in ITEMS} == {
        'A': 'TECHNICAL_FIT', 'B': 'TECHNICAL_FIT', 'E': 'TECHNICAL_FIT',
        'G': 'TECHNICAL_FIT', 'H': 'TECHNICAL_FIT',
        'C_prospect': 'BUSINESS_CASE', 'C_vendeur': 'BUSINESS_CASE', 'C_suivi': 'BUSINESS_CASE',
        'I': 'BUSINESS_CASE', 'D': 'BUSINESS_CASE', 'F': 'BUSINESS_CASE',
        'J': 'SOLUTION_VALIDATION', 'J2': 'SOLUTION_VALIDATION', 'K': 'BUSINESS_CASE',
    }


def test_an_unknown_expected_step_is_refused():
    data = copy.deepcopy(EXPECTED)
    data['items'][0]['expected_step'] = 'TECH_FIT'
    with pytest.raises(ValueError, match='expected_step'):
        scoring.validate_expected(data)


class TestStepMetric:

    def _score(self, persisted, version='v2'):
        return scoring.score_call(
            persisted=persisted, parsed={'signals': persisted},
            items=[i for i in EXPECTED['items'] if i['transcript'] == 'atelier'],
            transcript=_transcript('atelier'), prompt_version=version)

    def test_the_stored_step_name_is_compared_on_the_present(self):
        m = self._score([
            _ns('Envoyer le DPA et le SOC 2', 'EMAIL', suggested_decision_step='TECHNICAL_FIT'),
            _ns('Réunion sécurité avec Laurent Petit', 'MEETING',
                suggested_decision_step='BUSINESS_CASE'),
            _ns('Envoyer une première version du business case', 'TASK',
                suggested_decision_step=None),
        ])
        assert (m['A_step_ok'], m['A_step']) == (True, 'TECHNICAL_FIT')
        assert (m['B_step_ok'], m['B_step']) == (False, 'BUSINESS_CASE')
        assert (m['C_vendeur_step_ok'], m['C_vendeur_step']) == (False, '')   # no step = wrong
        assert m['C_prospect_step_ok'] is None                              # absent

    def test_na_on_the_baseline_prompt(self):
        m = self._score([_ns('Envoyer le DPA', 'EMAIL')], version='v1')
        assert m['A_step_ok'] is None


def test_the_recap_shows_the_step_column():
    from evals.next_steps.run_next_steps_eval import _recap
    metrics = scoring.score_call(
        persisted=[_ns('Envoyer le DPA', 'EMAIL', suggested_decision_step='TECHNICAL_FIT')],
        parsed=None, items=[i for i in EXPECTED['items'] if i['transcript'] == 'atelier'],
        transcript=_transcript('atelier'), prompt_version='v2')
    rows = [{'variant': 'atelier', 'call': 1, 'error': '', 'error_type': '',
             'duration_ms': 1, 'wall_ms': 1, **metrics}]
    lines = _recap(rows, 'v2')
    assert any(x.startswith('| variante | attendu |') and x.endswith('étape correcte (étapes vues) |')
               for x in lines)
    assert next(x for x in lines if x.startswith('| atelier | A |')).endswith(
        "| 1/1 {'TECHNICAL_FIT': 1} |")


# =============================================================================
# BILINGUAL MATCH -- titles of the real runs (v2 titles are in English)
# =============================================================================

# VERBATIM titles of the PO runs (distinct titles), with the item each one
# must match -- [] = a legitimate unmatched next step. No real title may
# fall on a wrong item.
REAL_TITLES = [
    # Terra v1 run, atelier.
    ('atelier', 'Envoyer le DPA et le rapport SOC 2 à Thomas', ['A']),
    # gpt-4o-mini v1 baseline, logistix/call_01: the merged one (F <- D).
    ('logistix', 'Prepare business case for Isabelle', ['F']),
    # v2 run out/20261023-125420, logistix (45 distinct titles).
    ('logistix', 'Send the SOC 2 security questionnaire', ['H']),
    ('logistix', 'Organize a security session with the DSI', ['G']),
    ('logistix', 'Meet Isabelle Roux to review the business case', ['D']),
    ('logistix', 'Prepare a quantified ROI business case for Isabelle Roux', ['F']),
    ('logistix', 'Meet with Isabelle Roux to review the business case', ['D']),
    ('logistix', 'Send Salesforce and Azure AD integration documentation', ['E']),
    ('logistix', 'Send Salesforce and Azure AD technical documentation', ['E']),
    ('logistix', 'Prepare a quantified ROI business case', ['F']),
    ('logistix', 'Send Salesforce and Azure AD SSO technical documentation', ['E']),
    ('logistix', "Organize a security session with Logistix's DSI", ['G']),
    ('logistix', 'Send technical integration documentation', ['E']),
    ('logistix', 'Send SOC 2 security questionnaire', ['H']),
    ('logistix', 'Hold business case meeting with Isabelle Roux', ['D']),
    ('logistix', 'Organize a security review session with the DSI', ['G']),
    ('logistix', 'Send technical integration documentation to Thomas', ['E']),
    ('logistix', 'Schedule a security review session with the DSI', ['G']),
    ('logistix', 'Send the SOC 2 questionnaire', ['H']),
    ('logistix', 'Obtain DAF validation of the ROI', []),
    ('logistix', "Follow up on the DAF's ROI validation", []),
    ('logistix', 'Prepare the ROI business case for Isabelle Roux', ['F']),
    ('logistix', 'Schedule business case meeting with Isabelle Roux', ['D']),
    ('logistix', 'Organize security session with Logistix DSI', ['G']),
    ('logistix', 'Send SOC 2 questionnaire before the DSI security session', ['H']),
    ('logistix', 'Prepare a quantified ROI business case for the CFO', ['F']),
    ('logistix', 'Send meeting recap', []),
    ('logistix', 'Prepare quantified ROI business case', ['F']),
    ('logistix', 'Prepare quantified ROI business case for Isabelle', ['F']),
    ('logistix', 'Send SOC 2 security questionnaire before DSI security session', ['H']),
    ('logistix', "Organize security review session with Logistix's DSI", ['G']),
    ('logistix', 'Schedule a security session with the DSI', ['G']),
    ('logistix', 'Schedule business-case meeting with Isabelle Roux', ['D']),
    ('logistix', 'Send SOC 2 questionnaire before the DSI security review', ['H']),
    ('logistix', 'Follow up on the Isabelle Roux business-case review', []),
    ('logistix', 'Send Salesforce integration and Azure AD SSO documentation', ['E']),
    ('logistix', 'Send Salesforce and Azure AD technical documentation to Thomas', ['E']),
    ('logistix', 'Prepare quantified ROI business case for Isabelle Roux', ['F']),
    ('logistix', 'Send the SOC 2 questionnaire for DSI security review', ['H']),
    ('logistix', 'Obtain DSI security validation', []),
    ('logistix', 'Prepare the ROI business case for Isabelle', ['F']),
    ('logistix', 'Meet with Isabelle to review the business case', ['D']),
    ('logistix', 'Prepare quantified ROI business case for Finance', ['F']),
    ('logistix', 'Schedule Finance meeting with Isabelle Roux', ['D']),
    ('logistix', 'Organize security review session with the DSI', ['G']),
    ('logistix', 'Prepare a quantified ROI business case for Isabelle', ['F']),
    ('logistix', 'Send a meeting recap to Logistix', []),
    # v2 run out/20261023-125420, atelier (61 distinct titles).
    ('atelier', 'Launch the pilot with Karim', ['J']),
    ('atelier', 'Train Karim for the pilot', ['J2']),
    ('atelier', 'Send the first version of the business case', ['C_vendeur']),
    ('atelier', 'Hold a security review meeting with Laurent Petit', ['B']),
    ('atelier', 'Send the DPA and SOC 2 report', ['A']),
    ('atelier', 'Validate the business case for the 2027 budget', ['K']),
    ('atelier', 'Hold security meeting with Laurent Petit', ['B']),
    ('atelier', 'Follow up on business case validation', ['C_suivi']),
    ('atelier', 'Hold a security meeting with Laurent Petit', ['B']),
    ('atelier', 'Send DPA and SOC 2 report to Logistix', ['A']),
    ('atelier', 'Launch pilot with Karim', ['J']),
    ('atelier', 'Follow up on business-case validation', ['C_suivi']),
    ('atelier', 'Deliver the final business case', ['I']),
    ('atelier', 'Send the final business case', ['I']),
    ('atelier', 'Present the final business case to the finance controller', ['C_prospect']),
    ('atelier', 'Present the final business case to Marc', ['C_prospect']),
    ('atelier', 'Present the final business case to the management controller and Marc', ['C_prospect']),
    ('atelier', 'Send the DPA and SOC 2 report to Thomas and Laurent', ['A']),
    ('atelier', 'Send first version of the business case', ['C_vendeur']),
    ('atelier', 'Send DPA and SOC 2 report to Thomas', ['A']),
    ('atelier', 'Send the DPA and SOC 2 report to Logistix', ['A']),
    ('atelier', 'Send DPA and SOC 2 report to Thomas and Laurent', ['A']),
    ('atelier', 'Hold security review meeting with Laurent Petit', ['B']),
    ('atelier', 'Send the final business case to Isabelle', ['I']),
    ('atelier', 'Present the final business case to the controller and Marc', ['C_prospect']),
    ('atelier', 'Follow up on the internal business-case review', ['C_suivi']),
    ('atelier', 'Launch a pilot with Karim in January', ['J']),
    ('atelier', 'Follow up on 2027 budget validation', ['C_suivi']),
    ('atelier', 'Launch a pilot with Karim', ['J']),
    ('atelier', 'Validate the business case before the 2027 budget closes', ['K']),
    ('atelier', 'Send the final business case for finance and executive review', ['I']),
    ('atelier', 'Validate the business case internally', ['K']),
    ('atelier', 'Follow up on internal business-case validation', ['C_suivi']),
    ('atelier', 'Send DPA and SOC 2 report for security review', ['A']),
    ('atelier', 'Send the first business-case version', ['C_vendeur']),
    ('atelier', 'Deliver the final business case for finance and executive review', ['I']),
    ('atelier', 'Present the business case to the controller and Marc', ['C_prospect']),
    ('atelier', 'Follow up on 2027 budget business-case validation', ['C_suivi']),
    ('atelier', 'Email the DPA and SOC 2 report to Thomas and Laurent', ['A']),
    ('atelier', 'Deliver the final business case to Isabelle', ['I']),
    ('atelier', 'Send final business case for internal presentation', ['I']),
    ('atelier', 'Follow up on the 2027 budget business-case validation', ['C_suivi']),
    ('atelier', 'Send final version of the business case', ['I']),
    ('atelier', 'Launch pilot with Karim in January', ['J']),
    ('atelier', 'Send the final business case for internal presentation', ['I']),
    ('atelier', 'Follow up on the business-case validation', ['C_suivi']),
    ('atelier', 'Schedule the security meeting with Laurent Petit', ['B']),
    ('atelier', 'Present the final business case to the finance controller and Marc', ['C_prospect']),
    ('atelier', 'Follow up on the final business-case presentation', ['C_suivi']),
    ('atelier', 'Complete internal business-case validation before budget closure', ['K']),
    ('atelier', 'Follow up on business-case validation before budget closure', ['C_suivi']),
    ('atelier', 'Present the business case to the finance controller and Marc', ['C_prospect']),
    ('atelier', 'Complete the 2027 budget decision', ['K']),
    ('atelier', 'Follow up on the 2027 budget decision', ['C_suivi']),
    ('atelier', 'Follow up on the business case validation', ['C_suivi']),
    ('atelier', 'Hold security review with Laurent Petit', ['B']),
    ('atelier', 'Present the business case to the controller', ['C_prospect']),
    ('atelier', 'Present the business case to Marc', ['C_prospect']),
    ('atelier', 'Hold a security review with Laurent Petit', ['B']),
    ('atelier', 'Follow up on the internal business-case presentation', ['C_suivi']),
    ('atelier', 'Launch the pilot with Karim in January', ['J']),
]


@pytest.mark.parametrize('transcript, title, expected', REAL_TITLES)
def test_real_titles(transcript, title, expected):
    assert _matching(title, transcript) == expected


# English titles in the style of the v2 run (NOT verbatim: the PO's lists of
# titles did not reach this session) -- one per item at least, and the
# ambiguous pairs D/F and I/C_prospect.
@pytest.mark.parametrize('transcript, title, expected', [
    ('atelier', 'Send DPA and SOC 2 report to Thomas before Friday', ['A']),
    ('atelier', 'Share hosting and compliance documents with Laurent', ['A']),
    ('atelier', 'Schedule security review meeting with Laurent Petit', ['B']),
    ('atelier', 'Hold security meeting with the CIO on a Tuesday', ['B']),
    ('atelier', 'Isabelle presents business case to management controller and Marc', ['C_prospect']),
    ('atelier', 'Internal validation of the business case by Isabelle', ['K']),
    ('atelier', 'Send first version of the business case to Isabelle', ['C_vendeur']),
    ('atelier', 'Draft the ROI business case', ['C_vendeur']),
    ('atelier', 'Follow up on business case validation with Isabelle', ['C_suivi']),
    ('atelier', 'Follow up on the DPA review', []),        # a follow-up of A, not C_suivi
    ('atelier', 'Send final business case to Isabelle before Nov 15', ['I']),
    ('atelier', 'Deliver the final version of the business case', ['I']),
    # I vs C_prospect: presenting / the controller / Marc -> C_prospect.
    ('atelier', 'Present final business case to the management controller', ['C_prospect']),
    ('atelier', 'Isabelle presents the final business case to Marc', ['C_prospect']),
    ('atelier', 'Launch pilot with Karim in January', ['J']),
    ('atelier', 'Train Karim and the key account team', ['J2']),
    # C_prospect needs the ACTION of presenting; I excludes presenting.
    ('atelier', 'Marc approves the 2027 budget', ['K']),
    ('atelier', 'Present the final business case internally', ['C_prospect']),
    # D vs F: the ACTION decides.
    ('logistix', 'Meeting with Isabelle Roux (CFO) on the business case', ['D']),
    ('logistix', 'Present the business case to the CFO', ['D']),
    ('logistix', 'Build ROI business case for Isabelle', ['F']),
    ('logistix', 'Draft business case with Claire for Isabelle', ['F']),
    # Meeting AND preparing in one title: a meeting -> D, never F (PO rule).
    ('logistix', 'Schedule meeting with Isabelle Roux to build the business case', ['D']),
    ('logistix', 'Send technical documentation to Thomas', ['E']),
    ('logistix', 'Schedule security session with the IT director', ['G']),
    ('logistix', 'Send SOC 2 questionnaire ahead of the security review', ['H']),
])
def test_english_titles(transcript, title, expected):
    assert _matching(title, transcript) == expected


def test_the_titles_report_lists_every_stored_title_with_its_items():
    from evals.next_steps.run_next_steps_eval import _titles_report
    records = [{'variant': 'logistix', 'persisted': [
        _ns('Meet Isabelle Roux to review the business case', 'MEETING'),
        _ns('Prepare business case for Isabelle', 'TASK'),
        _ns('Commander des croissants', 'TASK'),
    ]}, {'variant': 'logistix', 'persisted': [
        _ns('Meet Isabelle Roux to review the business case', 'MEETING')]}]
    lines = _titles_report(records)
    assert "| Meet Isabelle Roux to review the business case | 2 | {'MEETING': 2} | D |" in lines
    assert "| Prepare business case for Isabelle | 1 | {'TASK': 1} | F |" in lines
    assert "| Commander des croissants | 1 | {'TASK': 1} | — (non apparié) |" in lines


def test_launching_the_pilot_and_training_karim_are_two_items_no_duplicate():
    persisted = [_ns('Launch the pilot with Karim', 'TASK'), _ns('Train Karim for the pilot', 'TASK')]
    m = scoring.score_call(
        persisted=persisted, parsed={'signals': persisted},
        items=[i for i in EXPECTED['items'] if i['transcript'] == 'atelier'],
        transcript=_transcript('atelier'), prompt_version='v2')
    assert (m['J_present'], m['J2_present'], m['J_matches'], m['J2_matches']) == (True, True, 1, 1)
    assert (m['duplicates'], m['unmatched']) == (0, 0)


def test_k_the_prospect_validation_before_the_budget_closes():
    persisted = [_ns('Validate the business case for the 2027 budget', 'TASK', '2026-12-15',
                     carried_by_prospect=True, suggested_decision_step='BUSINESS_CASE')]
    m = scoring.score_call(
        persisted=persisted, parsed={'signals': persisted},
        items=[i for i in EXPECTED['items'] if i['transcript'] == 'atelier'],
        transcript=_transcript('atelier'), prompt_version='v2')
    assert (m['K_present'], m['K_type_ok'], m['K_date_in_window'], m['K_carried_ok'],
            m['K_step_ok']) == (True, True, True, True, True)
    assert m['C_suivi_present'] is False
