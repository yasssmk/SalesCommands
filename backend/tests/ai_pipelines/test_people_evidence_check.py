# backend/tests/ai_pipelines/test_people_evidence_check.py
"""
TD-279 V (PO) -- server check of the People proofs, through the REAL
pipeline path (FakeProvider -> persist_stage -> _build_people_data), before
the in-extraction dedup.

  a) the source_quote must be in the transcript (normalised) -> else role
     UNKNOWN, person KEPT, metadata.evidence_check quote_not_found;
  b) a SPEAKER's quote must be said by them or name them -> else UNKNOWN,
     quote_not_about_person;
  c) a transcript without speaker labels: only a) applies;
  d) per-status counter in the people sub_calls entry;
  + a stage sending a response schema mapped to a provider that does not
    support one (Claude) -> error at load.
"""

import json

import pytest

from app_modules.signals.constants import InfluenceLevel, PeopleRole


pytestmark = pytest.mark.django_db

TRANSCRIPT = '\n'.join([
    'Atelier projet - 2026/10/20 14:00 CEST - Transcript',
    '00:00:00',
    'Julien Moreau: Bonjour à tous, merci pour ce créneau.',
    "Claire Dubois: Honnêtement c'est moi qui ai poussé pour qu'on regarde votre solution.",
    'Claire Dubois: Isabelle Roux, notre DAF, tient le budget.',
    'Criminelle Husky: Je préparerai les chiffres pour Isabelle.',
    'Claire Dubois: Marc, notre DSI, validera la sécurité.',
    'Claire Dubois: Criminelle validera les hypothèses de coût.',
])
NO_LABELS = (
    'Compte rendu. Isabelle Roux tient le budget. '
    "Claire Dubois a poussé pour qu'on regarde la solution."
)


def _person(full_name, source_quote, role=PeopleRole.CHAMPION.value):
    return {
        'full_name': full_name,
        'role': role,
        'influence': InfluenceLevel.HIGH.value,
        'department': None,
        'notes': 'Observed in the call.',
        'source_quote': source_quote,
        'confidence': 0.9,
        'is_inferred': False,
    }


def _run(account, activity, user_a, fake_provider, people, transcript=TRANSCRIPT):
    from app_modules.ai_pipelines.pipelines.transcript_signals import (
        QualificationSignalsPipeline,
    )
    fake_provider.replies = {'people': json.dumps({'signals': people})}
    result = QualificationSignalsPipeline().run(
        transcript=transcript, activity=activity, user=user_a,
        client_id=account.client_id,
    )
    signals = result['signals_by_stage']['people']
    for signal in signals:
        signal.refresh_from_db()
    return signals, result['run']


def _by_name(signals):
    return {s.full_name: s for s in signals}


class TestRules:

    def test_a_quote_not_in_the_transcript_unknown_person_kept(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        [signal], _ = _run(account, activity, user_a, fake_provider, [
            _person('Claire Dubois', 'Je signe le bon de commande demain.'),
        ])
        assert signal.full_name == 'Claire Dubois'
        assert signal.role == PeopleRole.UNKNOWN
        assert signal.metadata['evidence_check'] == {
            'status': 'quote_not_found', 'rejected_role': 'CHAMPION'}

    def test_b_a_speaker_with_another_speakers_sentence_about_someone_else(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        [signal], _ = _run(account, activity, user_a, fake_provider, [
            _person('Criminelle Husky', 'Isabelle Roux, notre DAF, tient le budget.',
                    role=PeopleRole.ECONOMIC_BUYER.value),
        ])
        assert signal.role == PeopleRole.UNKNOWN
        assert signal.metadata['evidence_check'] == {
            'status': 'quote_not_about_person', 'rejected_role': 'ECONOMIC_BUYER'}

    def test_a_speaker_with_her_own_sentence_keeps_her_role(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        [signal], _ = _run(account, activity, user_a, fake_provider, [
            _person('Claire Dubois',
                    "c'est moi qui ai poussé pour qu'on regarde votre solution"),
        ])
        assert signal.role == PeopleRole.CHAMPION
        assert signal.metadata['evidence_check'] == {'status': 'ok'}

    def test_b_a_speaker_named_in_another_speakers_sentence_keeps_her_role(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        [signal], _ = _run(account, activity, user_a, fake_provider, [
            _person('Criminelle Husky', 'Criminelle validera les hypothèses de coût.',
                    role=PeopleRole.INFLUENCER.value),
        ])
        assert signal.role == PeopleRole.INFLUENCER
        assert signal.metadata['evidence_check'] == {'status': 'ok'}

    def test_a_cited_person_named_in_the_quote_keeps_his_role(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        [signal], _ = _run(account, activity, user_a, fake_provider, [
            _person('Marc', 'Marc, notre DSI, validera la sécurité.',
                    role=PeopleRole.DECISION_MAKER.value),
        ])
        assert signal.role == PeopleRole.DECISION_MAKER
        assert signal.metadata['evidence_check'] == {'status': 'ok'}

    def test_typographic_apostrophe_in_the_quote_is_found(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        # Quote with ’ (U+2019), transcript with '.
        [signal], _ = _run(account, activity, user_a, fake_provider, [
            _person('Claire Dubois',
                    'Honnêtement c’est moi qui ai poussé pour qu’on regarde votre solution.'),
        ])
        assert signal.role == PeopleRole.CHAMPION
        assert signal.metadata['evidence_check'] == {'status': 'ok'}

    def test_c_without_speaker_labels_only_rule_a_applies(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        signals, _ = _run(account, activity, user_a, fake_provider, [
            # About someone else, but no labels: b) does not apply.
            _person('Claire Dubois', 'Isabelle Roux tient le budget.'),
            # Not in the transcript: a) still applies.
            _person('Isabelle Roux', 'Isabelle valide tout.',
                    role=PeopleRole.ECONOMIC_BUYER.value),
        ], transcript=NO_LABELS)
        by_name = _by_name(signals)
        assert by_name['Claire Dubois'].role == PeopleRole.CHAMPION
        assert by_name['Claire Dubois'].metadata['evidence_check'] == {'status': 'ok'}
        assert by_name['Isabelle Roux'].role == PeopleRole.UNKNOWN
        assert by_name['Isabelle Roux'].metadata['evidence_check']['status'] == 'quote_not_found'

    def test_d_counter_per_cause_in_the_people_sub_call(
        self, account, activity, user_a, fake_provider, patch_active_provider,
    ):
        signals, run = _run(account, activity, user_a, fake_provider, [
            _person('Claire Dubois', "c'est moi qui ai poussé pour qu'on regarde votre solution"),
            _person('Criminelle Husky', 'Isabelle Roux, notre DAF, tient le budget.'),
            _person('Marc', 'Marc tranchera seul.'),
        ])
        assert len(signals) == 3      # nobody dropped
        [entry] = [c for c in run.sub_calls if c['stage'] == 'people']
        assert entry['evidence_check'] == {
            'ok': 1, 'quote_not_found': 1, 'quote_not_about_person': 1}
        others = [c for c in run.sub_calls if c['stage'] != 'people']
        assert all('evidence_check' not in c for c in others)


class TestText:

    def test_normalisation(self):
        from app_modules.ai_pipelines.services.transcript_text import normalize_text
        assert normalize_text('  « C’est   BON »… ') == "c'est bon"
        assert normalize_text('“Il a dit…  oui...”') == 'il a dit oui'
        assert normalize_text('l’équipe valide.') == "l'équipe valide"

    def test_speaker_labels_ignore_titles_and_timestamps(self):
        from app_modules.ai_pipelines.services.transcript_text import TranscriptText
        text = TranscriptText(TRANSCRIPT)
        assert text.labels == ['Julien Moreau', 'Claire Dubois', 'Criminelle Husky']
        assert text.said_by('Je préparerai les chiffres', 'Criminelle Husky')
        assert not text.said_by('Je préparerai les chiffres', 'Claire Dubois')
        assert not TranscriptText(NO_LABELS).has_speaker_labels


class TestLoadGuard:

    def test_a_schema_stage_mapped_to_claude_fails_at_load(self):
        from app_modules.ai_pipelines.pipelines import transcript_signals
        with pytest.raises(ImportError, match='does not support a response schema'):
            transcript_signals.check_stage_schemas(
                transcript_signals.STAGE_RESPONSE_SCHEMAS, {'people': 'claude'})

    def test_the_production_mapping_passes(self):
        from app_modules.ai_pipelines import config
        from app_modules.ai_pipelines.pipelines import transcript_signals
        transcript_signals.check_stage_schemas(
            transcript_signals.STAGE_RESPONSE_SCHEMAS, config.STAGE_PROVIDER)
